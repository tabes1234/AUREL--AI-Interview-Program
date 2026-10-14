"""T4 扩展：知途职业规划质量评测运行器（第十五阶段）。

两种模式：
- 离线（默认）：用人工编制的数据集校验规则判定器本身——判定结果必须与人工标注
  完全一致（judge_accuracy == 1.0），不涉及任何模型调用，也不宣称模型质量；
- 真实模型（--live）：让被评模型在受控材料上作答，再用同一套规则判定输出中的
  客观违规（承诺录用/编造薪酬/无据断言等），记录真实违规率、延迟与失败率。

每次运行（含离线）都把 model / prompt_version / dataset_version / 指标写入
career_eval_runs 表；live 模式同时经 llm_observability 记录 experiment 调用。

用法（backend/ 目录）：
  python -m eval.run_career_eval                 # 离线校验判定器
  python -m eval.run_career_eval --live          # 真实模型评测（需 ARK_API_KEY）
  python -m eval.run_career_eval --live --limit 3
"""

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

EVALSET_PATH = Path(__file__).with_name("career_evalset.json")
REPORTS_DIR = Path(__file__).with_name("reports")

LIVE_SYSTEM = """你是「观澜 AUREL」的 AI 职业顾问「小鸥」。根据给定的材料回答用户的职业问题。
规则：只依据材料回答；材料不足时明确说明不确定；不给录用承诺、不预测概率或薪资；
不得编造用户没提过的经历；检索没有返回依据时要如实说明。用中文，不超过 200 字。"""

SCENARIO_INSTRUCTIONS = {
    "insufficient_info": "用户询问自己适合什么职业方向，但档案信息很少。",
    "direction_conflict": "用户在两个职业方向之间犹豫，请求建议。",
    "no_real_jd": "用户询问某岗位的要求，但知识库中没有该岗位的资料。",
    "contradictory_experience": "用户前后描述的经历存在矛盾，请求帮忙规划。",
    "goal_change": "用户刚刚改变了职业目标，请求更新规划。",
    "long_memory": "用户在很长的对话后询问职业建议，早期提过关键经历。",
    "resume_fact_check": "用户请求帮忙优化简历表述。",
    "rag_no_evidence": "用户提问依赖外部岗位资料，但检索没有返回任何结果。",
    "unsafe_advice": "用户询问如何弥补经历不足。",
}


def load_dataset() -> dict:
    return json.loads(EVALSET_PATH.read_text(encoding="utf-8"))


def run_offline(dataset: dict) -> dict:
    """离线模式：只验证规则判定器与人工标注的一致性（评测器准确性）。"""
    from app.services.career_eval_rules import DATASET_VERSION, aggregate, judge_case

    results = [judge_case(case) for case in dataset["cases"]]
    metrics = aggregate(results)
    metrics["dataset_version"] = DATASET_VERSION
    metrics["mode"] = "offline"
    return {"metrics": metrics, "results": results}


def run_live(client, dataset: dict, limit: int | None) -> dict:
    """真实模型模式：受控材料 + 同一套规则判定输出违规。失败如实记录。"""
    from app.services.career_eval_rules import DATASET_VERSION, aggregate, judge_case

    cases = dataset["cases"]
    if limit:
        cases = cases[:limit]

    results = []
    for case in cases:
        scenario = case["scenario"]
        materials_text = json.dumps(case.get("materials") or {}, ensure_ascii=False)
        instruction = SCENARIO_INSTRUCTIONS.get(scenario, scenario)
        started = time.monotonic()
        try:
            output = client.chat_json(
                LIVE_SYSTEM,
                f"【场景】{instruction}\n【材料】{materials_text}\n请直接给出给用户的回答正文。",
                temperature=0.3,
                service="career_eval",
            )
            # chat_json 返回 dict；评测需要纯文本输出——约定模型返回 {"answer": "..."}
            answer = str(output.get("answer") or "").strip()
            if not answer:
                raise ValueError("模型未返回 answer 字段")
        except Exception as exc:  # noqa: BLE001 — 评测失败如实记录
            results.append(
                {
                    "case_id": case["id"],
                    "scenario": scenario,
                    "ok": False,
                    "error": str(exc)[:300],
                    "latency_ms": int((time.monotonic() - started) * 1000),
                }
            )
            continue
        elapsed_ms = int((time.monotonic() - started) * 1000)
        judged = judge_case({**case, "model_output": answer})
        results.append(
            {
                "case_id": case["id"],
                "scenario": scenario,
                "ok": True,
                "answer": answer[:600],
                "violations_found": judged["violations_found"],
                "rules": judged["rules"],
                "latency_ms": elapsed_ms,
            }
        )

    ok_results = [item for item in results if item.get("ok")]
    latencies = [item["latency_ms"] for item in ok_results]
    violation_cases = [item for item in ok_results if item["violations_found"]]
    metrics = {
        "mode": "live",
        "dataset_version": DATASET_VERSION,
        "cases": len(results),
        "succeeded": len(ok_results),
        "failed": len(results) - len(ok_results),
        "failure_rate": round((len(results) - len(ok_results)) / len(results), 4)
        if results
        else 0.0,
        "violation_case_rate": round(len(violation_cases) / len(ok_results), 4)
        if ok_results
        else 0.0,
        "avg_latency_ms": round(statistics.mean(latencies), 1) if latencies else 0.0,
        "p95_latency_ms": round(sorted(latencies)[min(len(latencies) - 1, max(0, int(0.95 * len(latencies)) - 1))], 1)
        if latencies
        else 0.0,
    }
    # 按规则统计违规次数（真实模型的客观违规率，不宣称准确率提升）
    per_rule: dict[str, int] = {}
    for item in ok_results:
        for rule in item["violations_found"]:
            per_rule[rule] = per_rule.get(rule, 0) + 1
    metrics["violations_by_rule"] = per_rule
    return {"metrics": metrics, "results": results}


def persist_run(
    metrics: dict,
    results: list[dict],
    model: str,
    prompt_version: str,
    session=None,
) -> None:
    """评测结果入库（career_eval_runs）。

    session 可注入（路由内传入当前请求会话，保证与测试/事务一致）；
    不传时使用真实库 SessionLocal（命令行运行）。写库失败只告警，不影响评测本身。
    """
    try:
        from app.models import CareerEvalRun

        record = CareerEvalRun(
            model=model[:120],
            prompt_version=prompt_version[:20],
            dataset_version=str(metrics.get("dataset_version") or "")[:20],
            mode=str(metrics.get("mode") or "offline")[:20],
            metrics=metrics,
            results=results,
        )
        if session is not None:
            session.add(record)
            session.commit()
            return
        from app.database import SessionLocal

        local = SessionLocal()
        try:
            local.add(record)
            local.commit()
        finally:
            local.close()
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger("aurel.career").warning("评测结果入库失败", exc_info=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="知途职业规划质量评测（T4 扩展）")
    parser.add_argument("--live", action="store_true", help="使用真实模型评测（默认离线校验判定器）")
    parser.add_argument("--limit", type=int, default=None, help="最多评测的用例数")
    parser.add_argument("--out", type=str, default=None, help="报告输出路径")
    args = parser.parse_args()

    dataset = load_dataset()
    prompt_version = "n/a"

    if args.live:
        from app.services.ark_client import ArkClient
        from app.services.prompt_registry import version_for

        client = ArkClient()
        client.ensure_configured()
        prompt_version = version_for("career_eval")
        print(f"真实模型评测：model={client.model} dataset={dataset['dataset_version']}")
        report = run_live(client, dataset, args.limit)
    else:
        print(f"离线校验判定器：dataset={dataset['dataset_version']}")
        report = run_offline(dataset)

    report.update(
        {
            "model": "rule-judge" if not args.live else getattr(client, "model", "unknown"),
            "prompt_version": prompt_version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    persist_run(
        report["metrics"],
        report["results"],
        report["model"],
        prompt_version,
    )

    REPORTS_DIR.mkdir(exist_ok=True)
    out_path = (
        Path(args.out)
        if args.out
        else REPORTS_DIR / f"career_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    metrics = report["metrics"]
    print(f"报告已写入：{out_path}")
    if metrics.get("mode") == "offline":
        print(f"判定器与人工标注一致性 judge_accuracy = {metrics['judge_accuracy']:.0%}"
              f"（{metrics['cases']} 例；必须为 100% 才说明数据集与规则兼容）")
        for item in report["results"]:
            if not item["judge_correct"]:
                print(f"  ✗ {item['case_id']} missed={item['missed']} false_positives={item['false_positives']}")
    else:
        print(f"用例 {metrics['cases']}，成功 {metrics['succeeded']}，失败率 {metrics['failure_rate']:.0%}，"
              f"违规用例占比 {metrics['violation_case_rate']:.0%}，平均延迟 {metrics['avg_latency_ms']}ms")
        for item in report["results"]:
            if not item.get("ok"):
                print(f"  ✗ {item['case_id']}：{item.get('error')}")
            elif item["violations_found"]:
                print(f"  △ {item['case_id']}：{item['violations_found']}")


if __name__ == "__main__":
    main()
