"""T4：固定测试集质量评测（真实模型调用）。

用法（在 backend/ 目录下）：
  python -m eval.run_eval                    # 全部套件
  python -m eval.run_eval --suite scoring    # 仅评分套件
  python -m eval.run_eval --limit 3          # 每个套件最多取 3 个用例

指标：
  - 解析成功率：模型输出通过后端 schema 校验的比例
  - 证据覆盖：评分维度均给出非空 evidence 的比例
  - 分数偏差：|模型总分 - 人工锚点分| 的平均值（越低越好）
  - 关键概念覆盖：must_cover 关键词在评分证据/输出中出现的比例
  - 延迟：平均 / P95 毫秒

报告写入 eval/reports/eval_<时间戳>.json，包含模型名与提示词版本，便于
跨模型 / 跨提示词版本横向对比（配合 LLM_EXPERIMENT_* 实验分流）。
"""

import argparse
import json
import math
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from app.services.ark_client import ArkClient, ArkError
from app.services.prompt_registry import PROMPT_VERSIONS
from app.services.question_generator import generate_questions
from app.services.scoring import score_interview

EVALSET_PATH = Path(__file__).with_name("evalset.json")
REPORTS_DIR = Path(__file__).with_name("reports")

DIFFICULTY_LABELS = {"basic": "基础", "intermediate": "进阶", "advanced": "挑战"}


def evaluate_scoring_case(client, case: dict) -> dict:
    """对单个评分用例执行真实评分并计算指标。不抛异常，失败如实返回。"""
    qa_pairs = [{"question": case["question"], "answer": case["answer"]}]
    started = time.monotonic()
    try:
        result = score_interview(
            client,
            position=case["position"],
            difficulty=DIFFICULTY_LABELS.get(case["difficulty"], case["difficulty"]),
            language=case["language"],
            qa_pairs=qa_pairs,
        )
    except ArkError as exc:
        return {
            "id": case["id"],
            "ok": False,
            "error": str(exc),
            "latency_ms": int((time.monotonic() - started) * 1000),
        }

    elapsed_ms = int((time.monotonic() - started) * 1000)
    evidence_ok = all(
        dim.evidence.strip() and dim.rationale.strip() for dim in result.dimensions
    )
    dimensions_covered = len(result.dimensions) >= 4
    reference = case.get("reference", {})
    anchor = reference.get("overall_score")
    deviation = abs(result.overall_score - anchor) if anchor is not None else None
    covered_keywords, missing_keywords = _keyword_coverage(
        reference.get("must_cover", []),
        json.dumps(
            {
                "summary": result.summary,
                "dimensions": [d.model_dump() for d in result.dimensions],
                "strengths": result.strengths,
                "improvements": [i.model_dump() for i in result.improvements],
            },
            ensure_ascii=False,
        ),
    )
    return {
        "id": case["id"],
        "ok": True,
        "overall_score": result.overall_score,
        "reference_score": anchor,
        "score_deviation": deviation,
        "dimensions_count": len(result.dimensions),
        "evidence_complete": evidence_ok,
        "dimensions_covered": dimensions_covered,
        "keywords_covered": covered_keywords,
        "keywords_missing": missing_keywords,
        "latency_ms": elapsed_ms,
    }


def evaluate_question_case(client, case: dict) -> dict:
    """对单个出题用例执行真实生成并计算指标。不抛异常，失败如实返回。"""
    started = time.monotonic()
    try:
        questions = generate_questions(
            client,
            position=case["position"],
            description=case.get("description", ""),
            difficulty=case["difficulty"],
            language=case["language"],
            question_count=case["question_count"],
        )
    except ArkError as exc:
        return {
            "id": case["id"],
            "ok": False,
            "error": str(exc),
            "latency_ms": int((time.monotonic() - started) * 1000),
        }
    elapsed_ms = int((time.monotonic() - started) * 1000)
    within_length = all(len(q) <= 80 for q in questions)
    return {
        "id": case["id"],
        "ok": True,
        "expected_count": case["question_count"],
        "actual_count": len(questions),
        "count_ok": len(questions) == case["question_count"],
        "length_ok": within_length,
        "questions": questions,
        "latency_ms": elapsed_ms,
    }


def _keyword_coverage(keywords: list, haystack: str) -> tuple[list[str], list[str]]:
    covered = [k for k in keywords if k in haystack]
    missing = [k for k in keywords if k not in haystack]
    return covered, missing


def aggregate(results: list[dict]) -> dict:
    ok_results = [r for r in results if r.get("ok")]
    latencies = [r["latency_ms"] for r in ok_results]
    summary: dict = {
        "cases": len(results),
        "parse_success": len(ok_results),
        "parse_success_rate": round(len(ok_results) / len(results), 4) if results else 0.0,
        "avg_latency_ms": round(statistics.mean(latencies), 1) if latencies else 0.0,
        "p95_latency_ms": round(sorted(latencies)[min(len(latencies) - 1, math.ceil(0.95 * len(latencies)) - 1)], 1)
        if latencies
        else 0.0,
    }
    deviations = [r["score_deviation"] for r in ok_results if r.get("score_deviation") is not None]
    if deviations:
        summary["avg_score_deviation"] = round(statistics.mean(deviations), 2)
    if ok_results and "evidence_complete" in ok_results[0]:
        summary["evidence_coverage"] = round(
            sum(1 for r in ok_results if r.get("evidence_complete")) / len(ok_results), 4
        )
        total_keywords = sum(
            len(r.get("keywords_covered", [])) + len(r.get("keywords_missing", []))
            for r in ok_results
        )
        covered_keywords = sum(len(r.get("keywords_covered", [])) for r in ok_results)
        if total_keywords:
            summary["keyword_coverage"] = round(covered_keywords / total_keywords, 4)
    if ok_results and "count_ok" in ok_results[0]:
        summary["count_accuracy"] = round(
            sum(1 for r in ok_results if r.get("count_ok")) / len(ok_results), 4
        )
    return summary


def run_suite(client, suite: str, limit: int | None) -> dict:
    evalset = json.loads(EVALSET_PATH.read_text(encoding="utf-8"))
    report: dict = {"suite": suite, "results": []}

    if suite in ("scoring", "all"):
        cases = evalset["scoring_cases"]
        if limit:
            cases = cases[:limit]
        results = [evaluate_scoring_case(client, case) for case in cases]
        report["results"].append({"name": "scoring", "metrics": aggregate(results), "cases": results})

    if suite in ("questions", "all"):
        cases = evalset["question_cases"]
        if limit:
            cases = cases[:limit]
        results = [evaluate_question_case(client, case) for case in cases]
        report["results"].append({"name": "questions", "metrics": aggregate(results), "cases": results})

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="T4 固定测试集质量评测（真实模型）")
    parser.add_argument("--suite", choices=["all", "scoring", "questions"], default="all")
    parser.add_argument("--limit", type=int, default=None, help="每个套件最多执行的用例数")
    parser.add_argument("--out", type=str, default=None, help="报告输出路径（默认 eval/reports/ 下按时间戳命名）")
    args = parser.parse_args()

    client = ArkClient()
    client.ensure_configured()
    print(f"评测开始：suite={args.suite} model={client.model}")
    print(f"提示词版本：{PROMPT_VERSIONS}")

    report = run_suite(client, args.suite, args.limit)
    report.update(
        {
            "model": client.model,
            "prompt_versions": PROMPT_VERSIONS,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    REPORTS_DIR.mkdir(exist_ok=True)
    out_path = Path(args.out) if args.out else REPORTS_DIR / f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"报告已写入：{out_path}")
    for block in report["results"]:
        metrics = block["metrics"]
        print(f"\n[{block['name']}] 用例 {metrics['cases']}，解析成功 {metrics['parse_success']}"
              f"（成功率 {metrics['parse_success_rate']:.0%}），平均延迟 {metrics['avg_latency_ms']}ms")
        if "avg_score_deviation" in metrics:
            print(f"  平均分数偏差 {metrics['avg_score_deviation']}，"
                  f"证据覆盖 {metrics.get('evidence_coverage', 0):.0%}，"
                  f"关键概念覆盖 {metrics.get('keyword_coverage', 0):.0%}")
        if "count_accuracy" in metrics:
            print(f"  出题数量准确率 {metrics['count_accuracy']:.0%}")
        for case in block["cases"]:
            if not case.get("ok"):
                print(f"  ✗ {case['id']}：{case.get('error')}")


if __name__ == "__main__":
    main()
