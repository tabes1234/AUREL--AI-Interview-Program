"""第十五阶段：知途高级能力测试。

覆盖：RAG 职业知识检索（同步/混合检索/过滤/过期降权/无据诚实）、能力图谱
（四态/来源/联动更新/用户修正规则/跨用户隔离）、多路径比较（保存/校验/来源）、
规划复盘与版本（历史不覆盖/数据依据/采纳建议）、记忆透明化与清除、成长反馈
空状态与真实趋势、评测（判定器一致性 + 离线入口）。
"""

import json
from datetime import timedelta
from pathlib import Path

from app.models import (
    CareerConversation,
    CareerMessage,
    CareerPlan,
    CareerPlanRevision,
    CareerProfile,
    CareerProfileFact,
    InterviewReport,
    InterviewTask,
    JobPosition,
    utcnow,
)
from app.services import career_retrieval, career_skill_graph
from eval.run_career_eval import EVALSET_PATH, load_dataset, run_offline
from tests.conftest import FakeArkClient, login_user, make_user

# ---------- RAG 职业知识检索 ----------


def _make_position(db_session, title="数据分析师", company="示例科技", **kwargs) -> JobPosition:
    position = JobPosition(
        company=company,
        title=title,
        required_skills_summary=kwargs.pop("required_skills_summary", "SQL、Python、统计分析、数据可视化"),
        responsibilities_summary=kwargs.pop(
            "responsibilities_summary", "负责业务数据的分析与洞察输出，支持运营决策"
        ),
        experience_summary=kwargs.pop("experience_summary", "应届或一年以内经验"),
        level=kwargs.pop("level", "校招"),
        content_hash=kwargs.pop("content_hash", f"hash-{title}-{company}"),
        source_type=kwargs.pop("source_type", "official_seed"),
        **kwargs,
    )
    db_session.add(position)
    db_session.commit()
    db_session.refresh(position)
    return position


def test_retrieval_sync_and_search_with_source(db_session, api_client):
    position = _make_position(db_session)
    response = api_client.post("/api/v1/career-guide/retrieval/sync")
    assert response.status_code == 200
    body = response.json()
    assert body["global_added"] >= 2  # 岗位摘要分块 + 指导资料种子

    search = api_client.post(
        "/api/v1/career-guide/retrieval/search",
        json={"query": "数据分析师需要什么技能"},
    )
    assert search.status_code == 200
    outcome = search.json()
    assert outcome["found"] is True
    hit = next(item for item in outcome["results"] if "数据分析师" in item["title"])
    assert hit["source_kind"] == "job_position"
    assert hit["source_url"] is None or isinstance(hit["source_url"], str)
    assert outcome["retrieval_meta"]["vector_kind"] == "local_hashed_term_vector"
    assert position.title in json.dumps(outcome, ensure_ascii=False)


def test_retrieval_filters_and_empty_honesty(db_session, api_client):
    _make_position(db_session)
    api_client.post("/api/v1/career-guide/retrieval/sync")

    filtered = api_client.post(
        "/api/v1/career-guide/retrieval/search",
        json={"query": "数据分析师", "experience_level": "社招"},
    )
    # 校招岗位经验水平不匹配 → 该岗位被过滤，仅可能命中不限的指导资料
    assert filtered.status_code == 200
    outcome = filtered.json()
    for item in outcome.get("results", []):
        assert item["experience_level"] in ("社招", "不限", "")

    none = api_client.post(
        "/api/v1/career-guide/retrieval/search",
        json={"query": "完全不存在的领域量子炼丹术"},
    )
    body = none.json()
    if body["found"] is False:
        assert "没有找到" in body["message"] or "未" in body["message"]


def test_retrieval_stale_downweight(db_session):
    position = _make_position(
        db_session,
        title="旧数据岗位",
        required_skills_summary="老旧技能栈描述",
        last_verified_at=utcnow() - timedelta(days=90),
    )
    career_retrieval.sync_global_index(db_session)
    outcome = career_retrieval.search_knowledge(
        db_session, user_id=1, query="老旧技能栈描述", top_k=5
    )
    assert outcome["found"] is True
    hit = next(item for item in outcome["results"] if item["source_id"] == str(position.id))
    assert hit["stale"] is True
    assert hit["rerank_boost"] < 0


def test_retrieval_user_scope_isolation(db_session, api_client):
    _make_position(db_session)
    other = make_user(db_session, username="intel-other", nickname="别人")
    profile = CareerProfile(user_id=other.id)
    db_session.add(profile)
    db_session.flush()
    db_session.add(
        CareerProfileFact(
            user_id=other.id,
            profile_id=profile.id,
            category="skill",
            content="独家私密技能：雪山独角兽工程",
            source_type="user_stated",
            confirmed=True,
        )
    )
    db_session.commit()
    career_retrieval.sync_global_index(db_session)
    career_retrieval.sync_user_index(db_session, other.id)

    response = api_client.post(
        "/api/v1/career-guide/retrieval/search",
        json={"query": "雪山独角兽工程"},
    )
    outcome = response.json()
    leaked = [
        item for item in outcome.get("results", []) if "雪山独角兽" in item["content"]
    ]
    assert leaked == []  # 他人档案分段绝不进入本人检索


# ---------- 能力图谱 ----------


def _make_report(db_session, user_id: int, scores: dict[str, float]) -> InterviewReport:
    task = InterviewTask(
        user_id=user_id,
        position="后端开发工程师",
        difficulty="intermediate",
        language="zh",
        question_count=2,
        status="completed",
    )
    db_session.add(task)
    db_session.flush()
    report = InterviewReport(
        task_id=task.id,
        overall_score=round(sum(scores.values()) / len(scores), 1),
        summary="整体表现稳定",
        dimensions=[
            {"name": name, "score": score, "evidence": "示例证据", "rationale": "示例理由"}
            for name, score in scores.items()
        ],
        strengths=["结构清晰"],
        improvements=[{"title": "加强原理", "detail": "补充底层机制"}],
        model_name="fake-model-test",
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)
    return report


def test_graph_update_after_interview_and_correction_rules(db_session, api_client):
    user = make_user(db_session)
    report = _make_report(
        db_session, user.id, {"内容深度": 80.0, "表达清晰": 60.0, "逻辑结构": 70.0}
    )
    outcome = career_skill_graph.update_after_interview(db_session, user.id, report)
    assert outcome["created_nodes"] > 0

    graph = api_client.get("/api/v1/career-guide/graph").json()
    statuses = {node["name"]: node["status"] for node in graph["nodes"]}
    assert statuses["内容深度"] == "verified"  # ≥75 已证实
    assert statuses["表达清晰"] == "pending"  # <75 尚待验证
    assert any(
        node["entity_type"] == "evidence" and "问澜报告" in node["name"]
        for node in graph["nodes"]
    )
    assert any(edge["relation"] == "proves" for edge in graph["edges"])
    assert any(edge["relation"] == "practice_for" for edge in graph["edges"])

    # 用户修正：verified 不能手工设置；verified 不能降级
    node_verified = next(node for node in graph["nodes"] if node["name"] == "内容深度")
    reject = api_client.patch(
        f"/api/v1/career-guide/graph/nodes/{node_verified['id']}",
        json={"status": "ai_inferred"},
    )
    assert reject.status_code == 422
    fake_mark = api_client.patch(
        "/api/v1/career-guide/graph/nodes/999999", json={"status": "user_stated"}
    )
    assert fake_mark.status_code == 404

    node_pending = next(node for node in graph["nodes"] if node["name"] == "表达清晰")
    confirm = api_client.patch(
        f"/api/v1/career-guide/graph/nodes/{node_pending['id']}",
        json={"status": "user_stated", "note": "我自己确认这项能力没问题"},
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "user_stated"


def test_graph_suggest_requires_quote_and_stays_unconfirmed(db_session, api_client):
    user = make_user(db_session)
    profile = CareerProfile(user_id=user.id)
    db_session.add(profile)
    db_session.flush()
    db_session.add(
        CareerProfileFact(
            user_id=user.id,
            profile_id=profile.id,
            category="skill",
            content="我熟练使用 React 与 TypeScript",
            source_type="user_stated",
            confirmed=True,
            quote="我熟练使用 React 与 TypeScript",
        )
    )
    db_session.commit()

    fake = FakeArkClient(
        [
            {
                "nodes": [
                    {
                        "entity_type": "skill",
                        "name": "前端框架开发",
                        "confidence": "high",
                        "quote": "我熟练使用 React 与 TypeScript",
                        "reason": "档案明确提到",
                    },
                    {
                        "entity_type": "skill",
                        "name": "分布式系统设计",
                        "confidence": "mid",
                        "quote": "这段话材料里根本没有",
                        "reason": "无依据的编造",
                    },
                ]
            }
        ]
    )
    from app.routers.interviews import get_ark_client

    import app.main as main_app

    main_app.app.dependency_overrides[get_ark_client] = lambda: fake
    try:
        graph = api_client.post("/api/v1/career-guide/graph/suggest").json()
    finally:
        main_app.app.dependency_overrides.pop(get_ark_client, None)

    names = {node["name"]: node for node in graph["nodes"]}
    assert "前端框架开发" in names
    assert names["前端框架开发"]["status"] == "ai_inferred"  # AI 提议永不自动转正
    assert "分布式系统设计" not in names  # 依据定位不到的直接丢弃


def test_graph_cross_user_isolation(db_session, api_client):
    user = make_user(db_session)
    report = _make_report(db_session, user.id, {"内容深度": 80.0})
    career_skill_graph.update_after_interview(db_session, user.id, report)
    node_id = career_skill_graph.get_graph(db_session, user.id)["nodes"][0]["id"]

    # 以另一个用户登录
    from tests.conftest import login_user

    other = make_user(db_session, username="intruder", nickname="闯入者")
    token = login_user(db_session, other)
    api_client.cookies.set("aurel_session", token)
    try:
        assert api_client.get("/api/v1/career-guide/graph").json()["nodes"] == []
        response = api_client.patch(
            f"/api/v1/career-guide/graph/nodes/{node_id}", json={"status": "user_stated"}
        )
        assert response.status_code == 404
        assert api_client.delete(f"/api/v1/career-guide/graph/nodes/{node_id}").status_code == 404
    finally:
        api_client.cookies.set("aurel_session", login_user(db_session, user))


# ---------- 多职业路径比较 ----------


def test_path_compare_saves_with_sources(db_session, api_client):
    _make_position(db_session, title="数据分析师")
    user = make_user(db_session)
    from tests.conftest import login_user

    token = login_user(db_session, user)
    api_client.cookies.set("aurel_session", token)

    fake = FakeArkClient(
        [
            {
                "directions": [
                    {
                        "name": "数据分析",
                        "relevance": "与用户的统计课程经历相关",
                        "skill_requirements": [
                            {"requirement": "SQL 与数据可视化", "source": "示例科技-数据分析师"}
                        ],
                        "evidence_gaps": ["缺少完整项目作品"],
                        "interests_constraints": [],
                        "learning_cost": "需要补统计基础",
                        "verification_actions": ["做一个小型分析项目"],
                    },
                    {
                        "name": "后端开发",
                        "relevance": "与已有开发练习相关",
                        "skill_requirements": [
                            {"requirement": "数据库与接口设计", "source": "通用经验，待核实"}
                        ],
                        "evidence_gaps": ["缺少真实接口项目"],
                        "interests_constraints": [],
                        "learning_cost": "已有部分基础",
                        "verification_actions": ["完成一次后端面试练习"],
                    },
                ],
                "comparison": {
                    "common": ["都需要工程基础"],
                    "diverge": ["统计深度 vs 系统设计"],
                    "recommendation": "先各做一次小成本验证",
                },
            }
        ]
    )
    from app.routers.interviews import get_ark_client
    import app.main as main_app

    main_app.app.dependency_overrides[get_ark_client] = lambda: fake
    try:
        response = api_client.post(
            "/api/v1/career-guide/paths/compare",
            json={"directions": ["数据分析", "后端开发"], "note": "希望工作强度可控"},
        )
    finally:
        main_app.app.dependency_overrides.pop(get_ark_client, None)

    assert response.status_code == 201, response.text
    record = response.json()
    assert len(record["directions"]) == 2
    assert record["directions"][0]["skill_requirements"][0]["source"] == "示例科技-数据分析师"
    assert "不构成" in record["data_basis"]["disclaimer"]
    # 知潮岗位来源进入数据依据
    assert any(
        source.get("title") == "数据分析师" for source in record["data_basis"]["job_sources"]
    )

    listed = api_client.get("/api/v1/career-guide/paths").json()
    assert len(listed) == 1

    # 校验：少于 2 个方向直接拒绝
    bad = api_client.post(
        "/api/v1/career-guide/paths/compare", json={"directions": ["只有一个"]}
    )
    assert bad.status_code == 422


def test_path_isolation_between_users(db_session, api_client):
    user = make_user(db_session)
    from tests.conftest import login_user

    token = login_user(db_session, user)
    api_client.cookies.set("aurel_session", token)
    from app.models import CareerPathComparison

    record = CareerPathComparison(
        user_id=user.id,
        title="A vs B",
        directions=[{"name": "A"}, {"name": "B"}],
    )
    db_session.add(record)
    db_session.commit()

    other = make_user(db_session, username="peeker", nickname="窥探者")
    api_client.cookies.set("aurel_session", login_user(db_session, other))
    assert api_client.get("/api/v1/career-guide/paths").json() == []
    assert api_client.get(f"/api/v1/career-guide/paths/{record.id}").status_code == 404
    assert api_client.delete(f"/api/v1/career-guide/paths/{record.id}").status_code == 404


# ---------- 规划复盘与版本 ----------


def _make_plan(db_session, user_id: int) -> CareerPlan:
    from app.models import CareerPlanAction

    plan = CareerPlan(user_id=user_id, title="数据方向成长计划", focus_role="数据分析师", version_no=1)
    db_session.add(plan)
    db_session.flush()
    db_session.add(
        CareerPlanAction(
            plan_id=plan.id,
            user_id=user_id,
            phase="7d",
            goal="完成一次数据分析模拟面试",
            steps="准备三道题；计时作答",
            position=0,
            due_at=utcnow() - timedelta(days=1),
        )
    )
    db_session.add(
        CareerPlanRevision(
            plan_id=plan.id,
            user_id=user_id,
            version_no=1,
            change_note="初始生成",
            snapshot={"title": "数据方向成长计划", "actions": []},
        )
    )
    db_session.commit()
    db_session.refresh(plan)
    return plan


def test_plan_review_creates_new_version_without_overwrite(db_session, api_client):
    user = make_user(db_session)
    from tests.conftest import login_user

    api_client.cookies.set("aurel_session", login_user(db_session, user))
    plan = _make_plan(db_session, user.id)

    fake = FakeArkClient(
        [
            {
                "review_summary": "任务已逾期未完成，建议调整期限并拆解步骤",
                "achievements": [],
                "blocked": ["模拟面试任务逾期"],
                "adjustments": [
                    {
                        "phase": "7d",
                        "goal": "完成一次数据分析模拟面试",
                        "steps": "先做知岗解析；再创建问澜练习",
                        "due_in_days": 3,
                        "reason": "原期限已过",
                    }
                ],
                "next_focus": ["补齐统计基础证据"],
            }
        ]
    )
    from app.routers.interviews import get_ark_client
    import app.main as main_app

    main_app.app.dependency_overrides[get_ark_client] = lambda: fake
    try:
        response = api_client.post(f"/api/v1/career-guide/plans/{plan.id}/review")
    finally:
        main_app.app.dependency_overrides.pop(get_ark_client, None)

    assert response.status_code == 200, response.text
    review = response.json()["review"]
    assert review["real_stats"]["overdue"] == 1  # 逾期来自真实数据

    revisions = api_client.get(f"/api/v1/career-guide/plans/{plan.id}/revisions").json()
    assert len(revisions) == 2  # 初始 + 复盘，历史不覆盖
    detail = api_client.get(
        f"/api/v1/career-guide/plans/{plan.id}/revisions/{revisions[0]['version_no']}"
    ).json()
    assert detail["snapshot"]["review"]["review_summary"]

    # 采纳建议 → 追加任务 + 新版本
    apply_response = api_client.post(
        f"/api/v1/career-guide/plans/{plan.id}/review/apply",
        json={"adjustments": review["adjustments"]},
    )
    assert apply_response.status_code == 200
    plan_after = apply_response.json()["plan"]
    assert plan_after["version_no"] == 3
    assert len(plan_after["actions"]) == 2


def test_plan_review_isolated(db_session, api_client):
    user = make_user(db_session)
    plan = _make_plan(db_session, user.id)
    other = make_user(db_session, username="stranger", nickname="陌生人")
    api_client.cookies.set("aurel_session", login_user(db_session, other))
    assert api_client.get(f"/api/v1/career-guide/plans/{plan.id}/revisions").status_code == 404
    assert api_client.post(f"/api/v1/career-guide/plans/{plan.id}/review").status_code == 404


# ---------- 记忆透明化与清除 ----------


def test_memory_usage_preview_and_clear(db_session, api_client):
    user = make_user(db_session)
    api_client.cookies.set("aurel_session", login_user(db_session, user))
    profile = CareerProfile(user_id=user.id)
    db_session.add(profile)
    db_session.flush()
    db_session.add(
        CareerProfileFact(
            user_id=user.id,
            profile_id=profile.id,
            category="major",
            content="统计学专业大三在读",
            source_type="user_stated",
            confirmed=True,
        )
    )
    conversation = CareerConversation(user_id=user.id, title="方向讨论")
    db_session.add(conversation)
    db_session.flush()
    db_session.add(
        CareerMessage(conversation_id=conversation.id, role="user", content="我在考虑转数据分析")
    )
    db_session.commit()

    usage = api_client.get(
        "/api/v1/career-guide/memory/usage", params={"query": "数据分析方向"}
    ).json()
    assert any("统计学" in fact["content"] for fact in usage["layers"]["confirmed_facts"])
    assert "assembled_context_preview" in usage

    cleared = api_client.delete("/api/v1/career-guide/memory").json()
    assert cleared["deleted_conversations"] == 1
    assert cleared["deleted_facts"] == 1
    # 清除后立即退出所有通道
    usage_after = api_client.get("/api/v1/career-guide/memory/usage").json()
    assert usage_after["layers"]["confirmed_facts"] == []
    assert usage_after["layers"]["related_history"] == []


# ---------- 成长反馈 ----------


def test_growth_feedback_empty_then_real(db_session, api_client):
    user = make_user(db_session)
    api_client.cookies.set("aurel_session", login_user(db_session, user))

    empty = api_client.get("/api/v1/career-guide/growth").json()
    assert empty["available"] is False
    assert "真实" in empty["message"]

    _make_report(db_session, user.id, {"内容深度": 80.0, "表达清晰": 70.0})
    real = api_client.get("/api/v1/career-guide/growth").json()
    assert real["available"] is True
    assert len(real["interview_scores"]) == 1
    assert real["interview_scores"][0]["score"] == 75.0


# ---------- 评测 ----------


def test_eval_judge_accuracy_on_human_dataset():
    """人工数据集上判定器必须与人工标注完全一致（judge_accuracy == 1.0）。"""
    dataset = load_dataset()
    scenarios = set(dataset["scenarios"])
    covered = {case["scenario"] for case in dataset["cases"]}
    assert covered == scenarios  # 九类场景全覆盖
    report = run_offline(dataset)
    assert report["metrics"]["judge_accuracy"] == 1.0, [
        (item["case_id"], item["missed"], item["false_positives"])
        for item in report["results"]
        if not item["judge_correct"]
    ]


def test_eval_offline_endpoint_persists(db_session, api_client):
    response = api_client.post("/api/v1/career-guide/eval/offline")
    assert response.status_code == 201
    assert response.json()["metrics"]["judge_accuracy"] == 1.0
    runs = api_client.get("/api/v1/career-guide/eval-runs").json()
    assert len(runs) == 1
    assert runs[0]["dataset_version"] == "career_evalset_v1.0"
    assert runs[0]["mode"] == "offline"


def test_evalset_file_integrity():
    assert EVALSET_PATH.exists()
    dataset = json.loads(EVALSET_PATH.read_text(encoding="utf-8"))
    ids = [case["id"] for case in dataset["cases"]]
    assert len(ids) == len(set(ids))
    for case in dataset["cases"]:
        assert case["model_output"].strip()
        assert isinstance(case["expect"].get("expected_violations", []), list)
