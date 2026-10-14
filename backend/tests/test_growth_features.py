"""回澜错题本（SM-2）/ 度衡限时挑战 / 成长热力图 的路由与服务测试。

AI 调用全部使用 FakeArkClient 注入（绝不发起真实模型调用）；
SM-2 调度直接断言间隔与 EF 的数值演进。
"""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app import models
from app.main import app
from app.models import utcnow
from app.routers.interviews import get_ark_client
from tests.conftest import make_user

# ---------- FakeArkClient：按 service 返回不同结构 ----------

CHALLENGE_OK = {
    "questions": [
        {
            "order_index": index,
            "content": f"场景题 {index}：请描述你的处理方式",
            "category": "场景",
            "dimension": "工程实践",
            "rubric": ["结构清晰", "有取舍"],
        }
        for index in range(1, 6)
    ]
}

SCORING_OK = {
    "summary": "回答完整，工程视角清晰。",
    "dimensions": [
        {"name": "内容深度", "score": 6.5, "evidence": "题1原文", "rationale": "有细节支撑"},
        {"name": "表达清晰", "score": 7.5, "evidence": "题2原文", "rationale": "结构分明"},
        {"name": "逻辑结构", "score": 7.0, "evidence": "题3原文", "rationale": "推理完整"},
        {"name": "岗位匹配", "score": 7.0, "evidence": "题4原文", "rationale": "经验对口"},
    ],
    "strengths": ["结构清晰"],
    "improvements": [{"title": "补充边界情况", "detail": "可以更全面"}],
}

GAP_OK = {
    "overall_note": "整体距岗位要求约一档，优先补齐数据敏感性与结构化表达。",
    "dimensions": [
        {"name": "逻辑结构", "target": 8.0, "gap_note": "先总后分，结论先行"},
        {"name": "数据敏感性", "target": 7.0, "gap_note": "从指标拆解练起"},
        {"name": "内容深度", "target": 7.5, "gap_note": "结合项目细节展开"},
    ],
}

WEEKLY_NOTE = {"note": "本周节奏平稳，下周挑一个最弱维度连练三天。"}


class FakeArkClient:
    model = "fake-model"

    def __init__(self, challenge=CHALLENGE_OK, scoring=SCORING_OK,
                 gap=GAP_OK, weekly=WEEKLY_NOTE):
        self._responses = {
            "question_set": challenge,
            "scoring": scoring,
            "gap_analysis": gap,
            "weekly_note": weekly,
        }

    def chat_json(self, system, user, *, temperature=0.3, service="unattributed"):
        return self._responses[service]

    def chat(self, system, user, *, temperature=0.7, service="unattributed"):
        return "{}"


@pytest.fixture()
def fake_ark():
    client = FakeArkClient()
    app.dependency_overrides[get_ark_client] = lambda: client
    yield client
    app.dependency_overrides.pop(get_ark_client, None)


def _question_fixture(db_session, user_id: int):
    """创建一个已完成的问澜任务（含题目与回答），返回 question id。"""
    task = models.InterviewTask(
        position="后端工程师",
        description="",
        difficulty="basic",
        language="zh",
        question_count=1,
        status="completed",
        user_id=user_id,
    )
    db_session.add(task)
    db_session.flush()
    question = models.InterviewQuestion(
        task_id=task.id, order_index=1, type="main", content="请解释事件循环的工作机制"
    )
    db_session.add(question)
    db_session.flush()
    db_session.add(
        models.InterviewAnswer(question_id=question.id, content="事件循环是……")
    )
    db_session.commit()
    return question.id


# ---------- 未登录访问 ----------


def test_growth_features_require_login(anon_client):
    assert anon_client.get("/api/v1/mistakes").status_code == 401
    assert anon_client.get("/api/v1/challenges").status_code == 401
    assert anon_client.get("/api/v1/stats/heatmap").status_code == 401


# ---------- 回澜错题本（SM-2）----------


def test_mistake_collect_review_sm2_flow(api_client, db_session):
    user = make_user(db_session)
    question_id = _question_fixture(db_session, user.id)

    collected = api_client.post(
        "/api/v1/mistakes", json={"question_id": question_id, "my_answer": ""}
    )
    assert collected.status_code == 201, collected.text
    card = collected.json()
    assert card["question_content"] == "请解释事件循环的工作机制"
    assert card["my_answer"] == "事件循环是……"  # 自动回填问澜回答
    assert card["is_due"] is True

    # 重复收集被拒绝
    assert (
        api_client.post("/api/v1/mistakes", json={"question_id": question_id}).status_code
        == 409
    )

    # 第一次复习（记得，q=4）：间隔 1 天，EF 下降
    reviewed = api_client.post(f"/api/v1/mistakes/{card['id']}/review", json={"grade": 4})
    assert reviewed.status_code == 200
    body = reviewed.json()
    assert body["repetitions"] == 1
    assert body["interval_days"] == 1
    assert body["ease_factor"] == pytest.approx(2.5 + 0.1 - (1 * (0.08 + 1 * 0.02)))
    assert body["is_due"] is False

    # 第二次（q=3）：间隔 6 天
    body = api_client.post(f"/api/v1/mistakes/{card['id']}/review", json={"grade": 3}).json()
    assert body["repetitions"] == 2
    assert body["interval_days"] == 6

    # 第三次（q=5）：间隔 = 上一间隔 × EF
    ef_after_two = body["ease_factor"]
    body = api_client.post(f"/api/v1/mistakes/{card['id']}/review", json={"grade": 5}).json()
    assert body["repetitions"] == 3
    assert body["interval_days"] == round(6 * ef_after_two)
    assert body["review_count"] == 3

    # 遗忘（q=0）：重置
    body = api_client.post(f"/api/v1/mistakes/{card['id']}/review", json={"grade": 0}).json()
    assert body["repetitions"] == 0
    assert body["interval_days"] == 1
    assert body["is_due"] is False  # 1 天后到期

    listing = api_client.get("/api/v1/mistakes").json()
    assert listing["total"] == 1

    assert api_client.delete(f"/api/v1/mistakes/{card['id']}").status_code == 204
    assert api_client.get("/api/v1/mistakes").json()["total"] == 0


def test_mistake_cannot_collect_other_users_question(api_client, db_session):
    owner = make_user(db_session, username="mistake-owner", nickname="题目主人")
    question_id = _question_fixture(db_session, owner.id)
    # api_client 是 tester@qq.com：不能收集别人的题目
    assert (
        api_client.post("/api/v1/mistakes", json={"question_id": question_id}).status_code
        == 404
    )


# ---------- 度衡限时挑战 ----------


def test_challenge_full_flow(api_client, fake_ark):
    created = api_client.post(
        "/api/v1/challenges",
        json={"position": "后端工程师", "difficulty": "intermediate", "question_count": 5,
              "duration_minutes": 15},
    )
    assert created.status_code == 201, created.text
    run = created.json()
    assert len(run["questions"]) == 5
    assert run["status"] == "created"
    run_id = run["id"]

    started = api_client.post(f"/api/v1/challenges/{run_id}/start")
    assert started.status_code == 200
    body = started.json()
    assert body["status"] == "in_progress"
    assert body["remaining_seconds"] is not None and 0 < body["remaining_seconds"] <= 900

    answers = [
        {"order_index": index, "answer": f"我对场景题 {index} 的回答"} for index in range(1, 6)
    ]
    submitted = api_client.post(f"/api/v1/challenges/{run_id}/submit", json={"answers": answers})
    assert submitted.status_code == 200, submitted.text
    body = submitted.json()
    assert body["status"] == "completed"
    assert body["overtime"] is False
    assert body["overall_score"] == pytest.approx(7.0)
    assert body["result"]["summary"] == SCORING_OK["summary"]

    history = api_client.get("/api/v1/challenges").json()
    assert [item["id"] for item in history] == [run_id]


def test_challenge_overtime_marked_by_server_clock(api_client, fake_ark, db_session):
    created = api_client.post(
        "/api/v1/challenges",
        json={"position": "测试岗", "difficulty": "basic", "question_count": 5,
              "duration_minutes": 5},
    )
    run = created.json()
    api_client.post(f"/api/v1/challenges/{run['id']}/start")

    # 直接把截止时间改到过去（模拟时间流逝），提交后服务端应标记 overtime
    stored = db_session.scalar(
        select(models.ChallengeRun).where(models.ChallengeRun.id == run["id"])
    )
    stored.deadline_at = utcnow() - timedelta(minutes=1)
    db_session.commit()

    submitted = api_client.post(
        f"/api/v1/challenges/{run['id']}/submit",
        json={"answers": [{"order_index": index, "answer": "答"} for index in range(1, 6)]},
    )
    assert submitted.status_code == 200
    assert submitted.json()["overtime"] is True


def test_challenge_rejects_double_submit(api_client, fake_ark):
    created = api_client.post(
        "/api/v1/challenges",
        json={"position": "测试岗", "difficulty": "basic", "question_count": 5,
              "duration_minutes": 5},
    )
    run_id = created.json()["id"]
    api_client.post(f"/api/v1/challenges/{run_id}/start")
    payload = {
        "answers": [
            {"order_index": index, "answer": f"答{index}"} for index in range(1, 6)
        ]
    }
    first = api_client.post(f"/api/v1/challenges/{run_id}/submit", json=payload)
    assert first.status_code == 200
    assert api_client.post(f"/api/v1/challenges/{run_id}/submit", json=payload).status_code == 409


# ---------- 成长热力图 ----------


def test_heatmap_counts_real_activity(api_client, db_session):
    user = make_user(db_session)
    _question_fixture(db_session, user.id)  # 造一条 completed 任务（今天）

    response = api_client.get("/api/v1/stats/heatmap")
    assert response.status_code == 200
    body = response.json()
    assert body["year"] == utcnow().year
    today = utcnow().date().isoformat()
    today_entry = next((day for day in body["days"] if day["date"] == today), None)
    assert today_entry is not None
    assert today_entry["count"] >= 1
    assert "interview" in today_entry["kinds"]
    assert body["streak"]["current"] >= 1


# ---------- 星图对照（观己 × 知岗差距分析） ----------


def _job_analysis_fixture(db_session, user_id: int) -> int:
    analysis = models.JobAnalysis(
        user_id=user_id,
        title="产品经理",
        jd_text="负责产品规划与数据分析，要求较强的逻辑结构与用户洞察能力。",
        jd_hash="hash-gap-test",
        version_no=1,
        status="ready",
        result={
            "position_name": "产品经理",
            "capability_dimensions": ["数据敏感性", "逻辑结构"],
            "keywords": ["PRD", "用户研究"],
        },
        model_name="fake-model",
    )
    db_session.add(analysis)
    db_session.commit()
    return analysis.id


def test_gap_analysis_fills_current_from_profile(api_client, fake_ark, db_session):
    user = make_user(db_session)
    analysis_id = _job_analysis_fixture(db_session, user.id)

    response = api_client.post("/api/v1/skills/gap-analysis", json={"job_analysis_id": analysis_id})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["position"] == "产品经理"
    assert body["model_name"] == "fake-model"
    # current 一律由服务端回填：无真实报告时如实记 0，不采信模型
    assert all(dim["current"] == 0.0 for dim in body["dimensions"])
    assert {dim["name"] for dim in body["dimensions"]} == {"逻辑结构", "数据敏感性", "内容深度"}
    assert len(body["overall_note"]) > 0

    # 他人解析不可见
    other = make_user(db_session, username="gap-other", nickname="另一位")
    other_analysis = models.JobAnalysis(
        user_id=other.id,
        title="别人的岗位",
        jd_text="",
        jd_hash="hash-gap-other",
        status="ready",
        result={"capability_dimensions": ["逻辑结构"], "keywords": []},
    )
    db_session.add(other_analysis)
    db_session.commit()
    assert (
        api_client.post(
            "/api/v1/skills/gap-analysis", json={"job_analysis_id": other_analysis.id}
        ).status_code
        == 404
    )


def test_gap_analysis_rejects_broken_ai_structure(api_client, fake_ark, db_session):
    from app.main import app as main_app
    from app.routers.interviews import get_ark_client as ark_dep

    user = make_user(db_session)
    analysis_id = _job_analysis_fixture(db_session, user.id)
    broken = FakeArkClient(gap={"overall_note": "缺维度", "dimensions": []})
    main_app.dependency_overrides[ark_dep] = lambda: broken
    try:
        response = api_client.post(
            "/api/v1/skills/gap-analysis", json={"job_analysis_id": analysis_id}
        )
        assert response.status_code == 502
        assert "结构不合格" in response.json()["detail"]
    finally:
        main_app.dependency_overrides.pop(ark_dep, None)


# ---------- 澜记周报 ----------


def test_weekly_report_aggregates_real_week(api_client, fake_ark, db_session):
    user = make_user(db_session)
    _question_fixture(db_session, user.id)  # 今天完成的问澜训练

    response = api_client.get("/api/v1/stats/weekly")
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["days"]) == 7
    assert body["totals"].get("interview", 0) >= 1
    assert body["interviews_completed"] >= 1
    assert body["average_score"] is None  # 本窗口的 fixture 无报告分数，如实为空
    assert body["active_days"] >= 1
    assert body["ai_note"] == WEEKLY_NOTE["note"]  # fake 客户端提供短评


def test_weekly_report_degrades_without_ai(api_client, db_session, monkeypatch):
    """未配置 ARK 时：统计数据照常返回，ai_note 如实为 null（绝不真调外部 API）。"""
    import app.services.ark_client as ark_module

    monkeypatch.setattr(ark_module, "ark_api_key", lambda: None)
    user = make_user(db_session)
    _question_fixture(db_session, user.id)

    response = api_client.get("/api/v1/stats/weekly")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["interviews_completed"] >= 1
    assert body["ai_note"] is None
