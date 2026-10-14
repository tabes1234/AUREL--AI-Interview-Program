"""面试任务 API 的完整流程测试（使用假模型客户端，不发起真实请求）。"""

from tests.conftest import (
    NO_FOLLOW_UP,
    VALID_SCORING,
    VALID_TASK,
    follow_up_response,
    question_generation_response,
    use_fake_client,
)


def test_create_interview_without_api_key_returns_503(api_client) -> None:
    from app.routers.interviews import get_ark_client
    from tests.conftest import NotConfiguredArkClient

    api_client.app.dependency_overrides[get_ark_client] = lambda: NotConfiguredArkClient()
    response = api_client.post("/api/v1/interviews", json=VALID_TASK)

    assert response.status_code == 503
    assert "未配置" in response.json()["detail"] or "ARK" in response.json()["detail"]


def test_ai_status_reports_not_configured(api_client) -> None:
    from app.routers.interviews import get_ark_client
    from tests.conftest import NotConfiguredArkClient

    api_client.app.dependency_overrides[get_ark_client] = lambda: NotConfiguredArkClient()
    response = api_client.get("/api/v1/ai/status")

    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is False
    assert "ARK_API_KEY" in data["message"] or "ARK_MODEL" in data["message"]


def test_ai_status_reports_configured(api_client) -> None:
    use_fake_client([])
    response = api_client.get("/api/v1/ai/status")

    assert response.status_code == 200
    data = response.json()
    assert data["configured"] is True
    assert data["model"] == "fake-model-test"


def test_create_interview_generates_questions(api_client) -> None:
    use_fake_client([question_generation_response(3)])
    response = api_client.post("/api/v1/interviews", json=VALID_TASK)

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "ready"
    assert len(data["questions"]) == 3
    assert data["current_question_id"] == data["questions"][0]["id"]
    assert all(q["type"] == "main" for q in data["questions"])


def test_create_interview_invalid_payload_returns_422(api_client) -> None:
    use_fake_client([])
    invalid = {**VALID_TASK, "position": "一"}
    response = api_client.post("/api/v1/interviews", json=invalid)
    assert response.status_code == 422


def test_get_missing_interview_returns_404(api_client) -> None:
    assert api_client.get("/api/v1/interviews/999").status_code == 404
    assert api_client.get("/api/v1/interviews/999/report").status_code == 404


def test_full_interview_flow_with_follow_up(api_client) -> None:
    """完整流程：创建 → 回答（含一次追问）→ 完成 → 报告。"""
    fake = use_fake_client([
        question_generation_response(3),  # 生成 3 题
        follow_up_response(),              # 第 1 题需要追问
        NO_FOLLOW_UP,                      # 第 2 题不追问
        NO_FOLLOW_UP,                      # 第 3 题不追问
        VALID_SCORING,                     # 评分
    ])

    created = api_client.post("/api/v1/interviews", json=VALID_TASK).json()
    task_id = created["id"]
    questions = created["questions"]

    # 回答第 1 题主问题 → 触发追问
    response = api_client.post(
        f"/api/v1/interviews/{task_id}/answers",
        json={"question_id": questions[0]["id"], "content": "我使用 React 三年，主要做过管理后台。"},
    ).json()
    assert response["next_question"] is not None
    assert response["next_question"]["type"] == "follow_up"
    assert response["next_question"]["parent_question_id"] == questions[0]["id"]
    follow_up_id = response["next_question"]["id"]

    # 回答追问 → 进入第 2 题
    response = api_client.post(
        f"/api/v1/interviews/{task_id}/answers",
        json={"question_id": follow_up_id, "content": "例如订单管理系统，负责表格与表单模块。"},
    ).json()
    assert response["next_question"]["id"] == questions[1]["id"]
    assert response["next_question"]["type"] == "main"

    # 回答第 2 题 → 不追问，进入第 3 题
    response = api_client.post(
        f"/api/v1/interviews/{task_id}/answers",
        json={"question_id": questions[1]["id"], "content": "首先分析需求，其次拆分组件，最后优化性能。"},
    ).json()
    assert response["next_question"]["id"] == questions[2]["id"]

    # 回答第 3 题 → 全部完成
    response = api_client.post(
        f"/api/v1/interviews/{task_id}/answers",
        json={"question_id": questions[2]["id"], "content": "我会持续学习，关注行业发展。"},
    ).json()
    assert response["all_answered"] is True
    assert response["next_question"] is None

    # 未完成前不应误报（此处已全部回答，可完成）
    finish = api_client.post(f"/api/v1/interviews/{task_id}/finish").json()
    assert finish["status"] == "completed"
    assert finish["report_id"] is not None

    # T1 报告字段完整性
    report = api_client.get(f"/api/v1/interviews/{task_id}/report").json()
    assert report["overall_score"] == 6.8  # (6+8+7+6)/4 四舍五入
    assert len(report["dimensions"]) == 4
    for dimension in report["dimensions"]:
        assert dimension["evidence"]
        assert dimension["rationale"]
    assert report["strengths"]
    assert report["improvements"]
    assert report["position"] == VALID_TASK["position"]
    assert report["model_name"] == fake.model

    # 详情里能看到全部问答（3 主问题 + 1 追问）
    detail = api_client.get(f"/api/v1/interviews/{task_id}").json()
    assert len(detail["questions"]) == 4
    assert detail["current_question_id"] is None

    # 列表包含该任务与总分
    tasks = api_client.get("/api/v1/interviews").json()
    assert any(t["id"] == task_id and t["overall_score"] == 6.8 for t in tasks)


def test_duplicate_answer_returns_409(api_client) -> None:
    use_fake_client([question_generation_response(3), NO_FOLLOW_UP])
    created = api_client.post("/api/v1/interviews", json=VALID_TASK).json()
    question_id = created["questions"][0]["id"]

    first = api_client.post(
        f"/api/v1/interviews/{created['id']}/answers",
        json={"question_id": question_id, "content": "回答一"},
    )
    assert first.status_code == 200

    second = api_client.post(
        f"/api/v1/interviews/{created['id']}/answers",
        json={"question_id": question_id, "content": "重复回答"},
    )
    assert second.status_code == 409


def test_answer_unknown_question_returns_404(api_client) -> None:
    use_fake_client([question_generation_response(3)])
    created = api_client.post("/api/v1/interviews", json=VALID_TASK).json()

    response = api_client.post(
        f"/api/v1/interviews/{created['id']}/answers",
        json={"question_id": 99999, "content": "回答"},
    )
    assert response.status_code == 404


def test_finish_before_all_answered_returns_409(api_client) -> None:
    use_fake_client([question_generation_response(3)])
    created = api_client.post("/api/v1/interviews", json=VALID_TASK).json()

    response = api_client.post(f"/api/v1/interviews/{created['id']}/finish")
    assert response.status_code == 409


def test_report_before_generation_returns_404(api_client) -> None:
    use_fake_client([question_generation_response(3)])
    created = api_client.post("/api/v1/interviews", json=VALID_TASK).json()

    response = api_client.get(f"/api/v1/interviews/{created['id']}/report")
    assert response.status_code == 404


def test_scoring_missing_dimension_fails_finish(api_client) -> None:
    """模型返回缺少维度时，finish 必须失败并保留任务状态，不得伪造报告。"""
    broken_scoring = {
        "summary": "评价",
        "dimensions": [
            {"name": "内容深度", "score": 6, "evidence": "e", "rationale": "r"},
        ],
        "strengths": ["a"],
        "improvements": [{"title": "t", "detail": "d"}],
    }
    use_fake_client([
        question_generation_response(3),
        NO_FOLLOW_UP,
        NO_FOLLOW_UP,
        NO_FOLLOW_UP,
        broken_scoring,
    ])

    created = api_client.post("/api/v1/interviews", json=VALID_TASK).json()
    task_id = created["id"]
    for question in created["questions"]:
        api_client.post(
            f"/api/v1/interviews/{task_id}/answers",
            json={"question_id": question["id"], "content": "测试回答内容"},
        )

    response = api_client.post(f"/api/v1/interviews/{task_id}/finish")
    assert response.status_code == 502
    assert "维度" in response.json()["detail"]

    detail = api_client.get(f"/api/v1/interviews/{task_id}").json()
    assert detail["status"] == "failed"
    assert detail["error_message"]
