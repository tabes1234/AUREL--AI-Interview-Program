"""第二阶段核心流程集成测试：真实调用火山方舟，走完整面试流程。

用途：手动验证（python scripts/integration_real.py），不进入 pytest。
会产生真实的模型调用费用，单次运行约 5-8 次模型请求。
"""

import json

import httpx

BASE = "http://127.0.0.1:8000/api/v1"

client = httpx.Client(timeout=180)


def step(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> None:
    step("1. 健康检查")
    health = client.get(f"{BASE}/health").json()
    print(json.dumps(health, ensure_ascii=False))
    assert health["status"] == "ok"

    step("2. AI 配置状态")
    ai = client.get(f"{BASE}/ai/status").json()
    print(json.dumps(ai, ensure_ascii=False))
    assert ai["configured"] is True, "AI 未配置，无法进行真实流程测试"

    step("3. 创建面试任务（真实生成问题）")
    created = client.post(
        f"{BASE}/interviews",
        json={
            "position": "前端工程师",
            "description": "负责 Web 前端开发，熟悉 React 与 TypeScript",
            "difficulty": "intermediate",
            "language": "zh",
            "question_count": 3,
        },
    )
    print(f"HTTP {created.status_code}")
    task = created.json()
    assert created.status_code == 201, task
    task_id = task["id"]
    for q in task["questions"]:
        print(f"  [{q['type']}] {q['content']}")
    assert len(task["questions"]) == 3

    step("4. 逐题回答（AI 实时判断是否追问）")
    answers = [
        "我用 React 和 TypeScript 开发了三年，主要负责中后台系统，做过表单引擎和数据可视化模块，对组件设计和状态管理比较熟悉。",
        "首先我会拆解需求把页面划分成独立组件，其次用 TypeScript 定义清晰的数据模型，最后通过代码评审保证质量，性能上会用懒加载和 memo 优化。",
        "我的优势是工程化经验扎实、乐于分享文档；不足是有时过于关注细节影响进度，我在通过明确优先级来改进。",
    ]
    round_index = 0
    guard = 0
    while guard < 12:
        guard += 1
        detail = client.get(f"{BASE}/interviews/{task_id}").json()
        current_id = detail["current_question_id"]
        if current_id is None:
            print("  全部问题已回答")
            break
        current = next(q for q in detail["questions"] if q["id"] == current_id)
        print(f"  回答 [{current['type']}] {current['content'][:40]}…")
        content = answers[min(round_index, len(answers) - 1)]
        round_index += 1
        response = client.post(
            f"{BASE}/interviews/{task_id}/answers",
            json={"question_id": current_id, "content": content},
        )
        print(f"  HTTP {response.status_code}")
        assert response.status_code == 200, response.text
        data = response.json()
        if data["next_question"]:
            print(f"  下一步：[{data['next_question']['type']}] {data['next_question']['content'][:40]}…")
        else:
            print("  下一步：全部完成")

    step("5. 完成面试并生成 T1 报告（真实评分）")
    finish = client.post(f"{BASE}/interviews/{task_id}/finish")
    print(f"HTTP {finish.status_code}")
    assert finish.status_code == 200, finish.text
    print(json.dumps(finish.json(), ensure_ascii=False))

    step("6. 获取报告")
    report = client.get(f"{BASE}/interviews/{task_id}/report")
    print(f"HTTP {report.status_code}")
    data = report.json()
    print(f"总分: {data['overall_score']}")
    print(f"模型: {data['model_name']}")
    print(f"总评: {data['summary'][:120]}…")
    for d in data["dimensions"]:
        print(f"  - {d['name']}: {d['score']} | 证据: {d['evidence'][:50]}… | 理由: {d['rationale'][:50]}…")
    print(f"亮点: {data['strengths']}")
    print(f"改进: {[i['title'] for i in data['improvements']]}")

    step("7. 历史列表")
    tasks = client.get(f"{BASE}/interviews").json()
    print(f"共 {len(tasks)} 个任务，本任务总分: {[t['overall_score'] for t in tasks if t['id'] == task_id]}")

    print("\n集成测试全部通过。")


if __name__ == "__main__":
    main()
