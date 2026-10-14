"""知潮（岗位资料库）与知岗/履历成章扩展测试。

覆盖：真实来源与时间字段、空状态、链接核验与过期标记、搜索过滤、收藏、
导入与重复检测、SSRF 防护、库内岗位→知岗解析/问澜/合契联动、用户修改解析结果、
模板参考来源、AI 岗位适配诊断不捏造事实、跨用户数据隔离。

模型调用全部使用 FakeArkClient，网络核验全部 mock，不发真实请求。
"""

import datetime

from fastapi.testclient import TestClient

from app.models import JobAnalysis, JobPosition, utcnow
from app.services import auth_service, job_library
from tests.conftest import (
    app,
    login_user,
    make_user,
    question_generation_response,
    use_fake_client,
)

MEITUAN_URL = "https://zhaopin.meituan.com/web/position?hiringType=4_1&pageNo=1"


def _seed(db_session) -> list[JobPosition]:
    created = job_library.seed_job_positions(db_session)
    assert created >= 8
    assert job_library.seed_job_positions(db_session) == 0  # 幂等：重复导入跳过
    return list(db_session.query(JobPosition).order_by(JobPosition.id))


def _position_by_title(db_session, title: str) -> JobPosition:
    return db_session.query(JobPosition).filter(JobPosition.title == title).first()


def _other_user_client(db_session) -> TestClient:
    other = make_user(db_session, username="library-other", nickname="另一位用户")
    client = TestClient(app)
    client.cookies.set(auth_service.SESSION_COOKIE_NAME, login_user(db_session, other))
    return client


def _create_resume(api_client: TestClient) -> dict:
    content = {
        "basics": {"name": "林澜", "summary": "三年 React 前端开发经验"},
        "work": [
            {
                "name": "云帆科技",
                "role": "前端工程师",
                "start": "2022-07",
                "end": "至今",
                "highlights": ["使用 React 与 TypeScript 重构管理后台，页面加载明显更快"],
            }
        ],
        "skills": [{"name": "React", "level": "精通", "detail": "Hooks 与状态管理"}],
    }
    response = api_client.post(
        "/api/v1/resumes", json={"title": "林澜的前端简历", "template_id": "tech", "content": content}
    )
    assert response.status_code == 201, response.text
    return response.json()


# ---------- 种子数据：真实来源与时间字段 ----------


class TestSeedIntegrity:
    def test_seed_positions_have_real_source_fields(self, db_session):
        positions = _seed(db_session)
        assert len(positions) >= 8
        meituan = _position_by_title(db_session, "AI全栈工程师")
        assert meituan is not None
        assert meituan.company == "美团"
        assert meituan.source_type == "official_seed"
        assert meituan.source_url == MEITUAN_URL
        assert meituan.display_permission == "summary_only"
        assert len(meituan.content_hash) == 64

    def test_missing_publish_time_is_honest_not_fabricated(self, db_session):
        """来源未提供发布时间 → published_at 为空并如实标注，不得伪造。"""
        _seed(db_session)
        meituan = _position_by_title(db_session, "AI全栈工程师")
        assert meituan.published_at is None
        assert "来源未提供发布时间" in meituan.published_note

    def test_unconfirmed_hiring_status_not_assumed_open(self, db_session):
        """无法确认是否仍在招聘 → 招聘状态未确认，不默认「正在招聘」。"""
        _seed(db_session)
        for position in db_session.query(JobPosition):
            assert position.hiring_status == "unconfirmed"

    def test_seed_records_verification_time(self, db_session):
        _seed(db_session)
        meituan = _position_by_title(db_session, "AI全栈工程师")
        assert meituan.last_verified_at is not None
        assert meituan.link_status == "ok"

    def test_full_jd_text_not_exposed_in_api(self, api_client, db_session):
        """原文全文不进入公开 API（display_permission=summary_only）。"""
        _seed(db_session)
        response = api_client.get("/api/v1/job-library")
        assert response.status_code == 200
        for item in response.json()["items"]:
            assert "jd_full_text" not in item


# ---------- 检索与空状态 ----------


class TestSearch:
    def test_list_returns_seeded_positions(self, api_client, db_session):
        _seed(db_session)
        data = api_client.get("/api/v1/job-library").json()
        assert data["total"] >= 8
        assert any("美团" in i["company"] for i in data["items"])

    def test_keyword_search(self, api_client, db_session):
        _seed(db_session)
        data = api_client.get("/api/v1/job-library", params={"q": "AI全栈"}).json()
        assert data["total"] >= 1
        assert all("AI全栈" in i["title"] or "AI全栈" in i["responsibilities_summary"] for i in data["items"])

    def test_filter_by_industry_and_company(self, api_client, db_session):
        _seed(db_session)
        data = api_client.get(
            "/api/v1/job-library", params={"industry_id": "internet-software-ai", "company": "美团"}
        ).json()
        assert data["total"] >= 4
        assert all(i["company"] == "美团" for i in data["items"])

    def test_empty_state_when_no_match(self, api_client, db_session):
        """无匹配数据 → 空列表（前端显示空状态），不允许假数据填充。"""
        _seed(db_session)
        data = api_client.get("/api/v1/job-library", params={"q": "完全不存在的岗位XYZ"}).json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_search_requires_login(self, anon_client, db_session):
        _seed(db_session)
        assert anon_client.get("/api/v1/job-library").status_code == 401


# ---------- 收藏 ----------


class TestFavorites:
    def test_favorite_lifecycle_and_isolation(self, api_client, db_session):
        _seed(db_session)
        position = _position_by_title(db_session, "AI全栈工程师")

        assert api_client.post(f"/api/v1/job-library/{position.id}/favorite").status_code == 204
        favorites = api_client.get("/api/v1/job-library/favorites").json()
        assert favorites["total"] == 1
        assert favorites["items"][0]["id"] == position.id
        assert favorites["items"][0]["is_favorited"] is True

        # 其他用户看不到该收藏
        other = _other_user_client(db_session)
        assert other.get("/api/v1/job-library/favorites").json()["total"] == 0

        assert api_client.delete(f"/api/v1/job-library/{position.id}/favorite").status_code == 204
        assert api_client.get("/api/v1/job-library/favorites").json()["total"] == 0

    def test_favorite_missing_position_404(self, api_client):
        assert api_client.post("/api/v1/job-library/99999/favorite").status_code == 404


# ---------- 导入与重复检测 ----------


class TestImport:
    def _payload(self, **overrides) -> dict:
        base = {
            "company": "澜舟科技",
            "title": "LLM 应用工程师",
            "location": "杭州市",
            "level": "校园招聘",
            "industry_id": "internet-software-ai",
            "occupation_id": "internet-software-ai.llm-application-engineer",
            "source_url": "https://careers.example-official.com/positions/1",
            "responsibilities_summary": "负责大模型应用的设计与开发，探索 Agent 编排在业务中的落地。",
            "required_skills_summary": "熟悉 Python、FastAPI 与 RAG 检索。",
            "hiring_status": "unconfirmed",
        }
        base.update(overrides)
        return base

    def test_import_creates_position_with_source(self, api_client, db_session):
        response = api_client.post("/api/v1/job-library", json=self._payload())
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["is_duplicate"] is False
        assert body["position"]["source_type"] == "user_import"
        assert body["position"]["hiring_status"] == "unconfirmed"

    def test_duplicate_import_detected_by_content_hash(self, api_client, db_session):
        first = api_client.post("/api/v1/job-library", json=self._payload())
        second = api_client.post("/api/v1/job-library", json=self._payload())
        assert first.status_code == 201 and second.status_code == 201
        assert second.json()["is_duplicate"] is True
        assert second.json()["position"]["id"] == first.json()["position"]["id"]

    def test_import_without_url_is_manual_and_rejected_if_empty(self, api_client, db_session):
        manual = api_client.post(
            "/api/v1/job-library", json=self._payload(source_url=None)
        )
        assert manual.status_code == 201
        assert manual.json()["position"]["source_type"] == "manual"

        empty = api_client.post(
            "/api/v1/job-library",
            json=self._payload(
                source_url=None,
                responsibilities_summary="",
                required_skills_summary="",
            ),
        )
        assert empty.status_code == 422

    def test_import_rejects_private_and_non_http_urls(self, api_client, db_session):
        for bad_url in ("http://127.0.0.1/positions/1", "ftp://example.com/1", "not-a-url"):
            response = api_client.post("/api/v1/job-library", json=self._payload(source_url=bad_url))
            assert response.status_code == 422, bad_url

    def test_import_validates_catalog_references(self, api_client):
        response = api_client.post(
            "/api/v1/job-library", json=self._payload(industry_id="not-a-real-industry")
        )
        assert response.status_code == 422

    def test_import_requires_login(self, anon_client):
        assert anon_client.post("/api/v1/job-library", json={}).status_code == 401


# ---------- 来源链接核验与过期标记 ----------


class TestVerify:
    def test_verify_ok_link(self, api_client, db_session, monkeypatch):
        _seed(db_session)
        position = _position_by_title(db_session, "AI全栈工程师")

        class FakeResponse:
            status_code = 200

        monkeypatch.setattr(job_library.httpx, "get", lambda *a, **k: FakeResponse())
        data = api_client.post(f"/api/v1/job-library/{position.id}/verify").json()
        assert data["link_status"] == "ok"
        assert data["last_verified_at"] is not None

    def test_verify_dead_link_marked(self, api_client, db_session, monkeypatch):
        _seed(db_session)
        position = _position_by_title(db_session, "AI全栈工程师")

        class FakeResponse:
            status_code = 404

        monkeypatch.setattr(job_library.httpx, "get", lambda *a, **k: FakeResponse())
        data = api_client.post(f"/api/v1/job-library/{position.id}/verify").json()
        assert data["link_status"] == "dead"
        assert "失效" in data["verified_note"]

    def test_verify_network_failure_marked_stale(self, api_client, db_session, monkeypatch):
        _seed(db_session)
        position = _position_by_title(db_session, "AI全栈工程师")

        def _raise(*args, **kwargs):
            raise job_library.httpx.ConnectError("connection refused")

        monkeypatch.setattr(job_library.httpx, "get", _raise)
        data = api_client.post(f"/api/v1/job-library/{position.id}/verify").json()
        assert data["link_status"] == "stale"

    def test_verify_does_not_change_hiring_status(self, api_client, db_session, monkeypatch):
        """链接可打开 ≠ 正在招聘：核验不得擅自改变招聘状态。"""
        _seed(db_session)
        position = _position_by_title(db_session, "AI全栈工程师")

        class FakeResponse:
            status_code = 200

        monkeypatch.setattr(job_library.httpx, "get", lambda *a, **k: FakeResponse())
        data = api_client.post(f"/api/v1/job-library/{position.id}/verify").json()
        assert data["hiring_status"] == "unconfirmed"

    def test_long_unverified_marked_possibly_expired(self, api_client, db_session):
        """超过核验周期未核验 → 「可能已过期」提示（stale_hint）。"""
        _seed(db_session)
        position = _position_by_title(db_session, "AI全栈工程师")
        position.last_verified_at = utcnow() - datetime.timedelta(days=31)
        db_session.commit()

        data = api_client.get(f"/api/v1/job-library/{position.id}").json()
        assert data["stale_hint"] is True

    def test_verify_rejects_position_without_url(self, api_client, db_session):
        payload = {
            "company": "澜舟科技",
            "title": "数据标注专员",
            "responsibilities_summary": "负责多模态数据标注规范制定与质量抽检。",
            "source_url": None,
        }
        created = api_client.post("/api/v1/job-library", json=payload).json()
        response = api_client.post(f"/api/v1/job-library/{created['position']['id']}/verify")
        assert response.status_code == 422


# ---------- 库内岗位 → 知岗 / 问澜 / 合契联动 ----------


def _valid_analysis_payload() -> dict:
    return {
        "position_name": "AI全栈工程师",
        "industry": "互联网",
        "responsibilities": [
            {"text": "负责 AI 产品功能的前端界面与后端服务", "evidence": "负责 AI 产品功能的前端界面（Web/小程序）与后端服务的设计与实现"},
        ],
        "required_skills": [{"text": "React", "evidence": "AI全栈工程师"}],
        "preferred_skills": [],
        "experience_requirement": {"text": "应届毕业生", "evidence": "校园招聘"},
        "education_requirement": {"text": "未明确说明", "evidence": None},
        "tools": [],
        "capability_dimensions": ["全栈开发", "系统设计"],
        "interview_directions": ["前后端协作", "AI 应用集成"],
        "keywords": ["AI", "全栈", "React"],
    }


class TestPositionLinks:
    def test_analyze_from_position_and_reuse(self, api_client, db_session):
        _seed(db_session)
        position = _position_by_title(db_session, "AI全栈工程师")
        fake = use_fake_client([_valid_analysis_payload()])

        first = api_client.post(f"/api/v1/job-library/{position.id}/analyze", json={})
        assert first.status_code == 201, first.text
        assert first.json()["reused"] is False

        # 复用：不再消耗模型响应（若再次调用模型会触发 FakeArkClient 断言）
        second = api_client.post(f"/api/v1/job-library/{position.id}/analyze", json={})
        assert second.status_code == 201
        assert second.json()["reused"] is True
        assert second.json()["job_analysis_id"] == first.json()["job_analysis_id"]
        assert len(fake.calls) == 1

        analysis = db_session.get(JobAnalysis, first.json()["job_analysis_id"])
        assert analysis.source_job_id == position.id
        assert analysis.user_id is not None

    def test_analyze_from_position_records_evidence_check(self, api_client, db_session):
        _seed(db_session)
        position = _position_by_title(db_session, "AI全栈工程师")
        use_fake_client([_valid_analysis_payload()])
        data = api_client.post(f"/api/v1/job-library/{position.id}/analyze", json={}).json()
        detail = api_client.get(f"/api/v1/jobs/analyses/{data['job_analysis_id']}").json()
        assert detail["source_job_id"] == position.id
        assert detail["result"]["required_skills"][0]["is_inferred"] is False

    def test_interview_task_from_position(self, api_client, db_session):
        _seed(db_session)
        position = _position_by_title(db_session, "AI全栈工程师")
        use_fake_client([_valid_analysis_payload(), question_generation_response(3)])
        response = api_client.post(f"/api/v1/job-library/{position.id}/interview-task", json={})
        assert response.status_code == 201, response.text
        task = response.json()
        assert task["position"] == "AI全栈工程师"
        assert len(task["questions"]) == 3

    def test_match_from_position_with_resume(self, api_client, db_session):
        _seed(db_session)
        position = _position_by_title(db_session, "AI全栈工程师")
        resume = _create_resume(api_client)
        use_fake_client(
            [_valid_analysis_payload(), {"suggestions": ["补充全栈项目的量化结果（真实数据）"]}]
        )
        response = api_client.post(
            f"/api/v1/job-library/{position.id}/match", json={"resume_id": resume["id"]}
        )
        assert response.status_code == 201, response.text
        match = response.json()
        assert "React" in [m["skill"] for m in match["matched_skills"]]
        assert "不代表获得工作的概率" in match["score_note"]

    def test_position_links_isolated_between_users(self, api_client, db_session):
        _seed(db_session)
        position = _position_by_title(db_session, "AI全栈工程师")
        use_fake_client([_valid_analysis_payload()])
        first = api_client.post(f"/api/v1/job-library/{position.id}/analyze", json={}).json()

        other = _other_user_client(db_session)
        use_fake_client([_valid_analysis_payload()])
        second = other.post(f"/api/v1/job-library/{position.id}/analyze", json={}).json()
        # 不同用户各自解析，互不复用对方的记录
        assert second["job_analysis_id"] != first["job_analysis_id"]


# ---------- 库内岗位 → 知途规划联动 ----------


CAREER_PLAN_PAYLOAD = {
    "title": "AI全栈工程师准备计划",
    "focus_role": "AI全栈工程师",
    "situation": "目标岗位来自知潮资料库，解析依据已关联。",
    "actions": [
        {"phase": "7d", "goal": "梳理全栈技术栈清单", "steps": "对照岗位要求逐项标注", "due_in_days": 5},
        {"phase": "30d", "goal": "完成一个 AI 全栈小项目", "steps": "前端+后端+模型调用", "due_in_days": 25},
        {"phase": "90d", "goal": "完成两次问澜模拟面试", "steps": "生成题集并复盘", "due_in_days": 80},
    ],
}


class TestCareerPlanLink:
    def test_career_plan_from_position_creates_and_reuses_analysis(self, api_client, db_session):
        _seed(db_session)
        position = _position_by_title(db_session, "AI全栈工程师")
        fake = use_fake_client([_valid_analysis_payload(), CAREER_PLAN_PAYLOAD])

        first = api_client.post(f"/api/v1/job-library/{position.id}/career-plan", json={})
        assert first.status_code == 201, first.text
        data = first.json()
        assert data["reused_analysis"] is False
        assert data["plan_title"] == "AI全栈工程师准备计划"
        assert data["focus_role"] == "AI全栈工程师"
        # 规划真实落库：属于当前用户、携带 7/30/90 行动、数据版本记录岗位解析依据
        from app.models import CareerPlan

        plan = db_session.get(CareerPlan, data["plan_id"])
        assert plan is not None
        assert plan.user_id is not None
        assert plan.data_basis["job_analysis_id"] == data["job_analysis_id"]
        assert plan.data_basis["job_title"] == "AI全栈工程师"
        assert len(plan.actions) == 3
        analysis = db_session.get(JobAnalysis, data["job_analysis_id"])
        assert analysis.source_job_id == position.id

        # 再次调用：复用已有解析（只消耗一次新的规划响应），生成独立新计划
        fake2 = use_fake_client([CAREER_PLAN_PAYLOAD])
        second = api_client.post(f"/api/v1/job-library/{position.id}/career-plan", json={})
        assert second.status_code == 201, second.text
        assert second.json()["reused_analysis"] is True
        assert second.json()["job_analysis_id"] == data["job_analysis_id"]
        assert second.json()["plan_id"] != data["plan_id"]
        assert len(fake2.calls) == 1

    def test_career_plan_isolated_between_users(self, api_client, db_session):
        _seed(db_session)
        position = _position_by_title(db_session, "AI全栈工程师")
        use_fake_client([_valid_analysis_payload(), CAREER_PLAN_PAYLOAD])
        mine = api_client.post(f"/api/v1/job-library/{position.id}/career-plan", json={}).json()

        other = _other_user_client(db_session)
        other_list = other.get("/api/v1/career-guide/plans").json()
        assert all(item["id"] != mine["plan_id"] for item in other_list)

        # 其他用户对同一公开岗位生成自己的规划，互不影响
        use_fake_client([_valid_analysis_payload(), CAREER_PLAN_PAYLOAD])
        theirs = other.post(f"/api/v1/job-library/{position.id}/career-plan", json={})
        assert theirs.status_code == 201, theirs.text
        assert theirs.json()["plan_id"] != mine["plan_id"]


# ---------- 用户修改知岗解析结果 ----------


class TestUpdateAnalysis:
    def _analyze(self, api_client) -> dict:
        use_fake_client([_valid_analysis_payload()])
        response = api_client.post("/api/v1/jobs/analyze", json={"jd_text": "岗位名称：AI全栈工程师。负责 AI 产品功能的前端界面（Web/小程序）与后端服务的设计与实现。岗位级别：校园招聘。"})
        assert response.status_code == 201, response.text
        return response.json()

    def test_user_edit_marks_and_keeps_evidence_check(self, api_client, db_session):
        analysis = self._analyze(api_client)
        edited = dict(analysis["result"])
        edited["position_name"] = "AI全栈工程师（高级）"  # 用户修正岗位名
        response = api_client.patch(f"/api/v1/jobs/analyses/{analysis['id']}", json={"result": edited})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["user_edited"] is True
        assert body["result"]["position_name"] == "AI全栈工程师（高级）"
        # 证据核验标准不降低：无证据的结论仍标记为推断
        assert body["result"]["education_requirement"]["is_inferred"] is True

    def test_user_edit_rejects_invalid_structure(self, api_client):
        analysis = self._analyze(api_client)
        response = api_client.patch(
            f"/api/v1/jobs/analyses/{analysis['id']}", json={"result": {"position_name": "缺字段"}}
        )
        assert response.status_code == 422

    def test_user_edit_isolated_between_users(self, api_client, db_session):
        analysis = self._analyze(api_client)
        other = _other_user_client(db_session)
        assert (
            other.patch(
                f"/api/v1/jobs/analyses/{analysis['id']}", json={"result": analysis["result"]}
            ).status_code
            == 404
        )


# ---------- 履历成章：模板参考来源与岗位适配诊断 ----------


class TestResumeEnhancements:
    def test_template_sources_exposed(self, api_client):
        response = api_client.get("/api/v1/resumes/template-sources")
        assert response.status_code == 200
        sources = response.json()
        assert len(sources) == 2
        names = " ".join(s["name"] for s in sources)
        assert "清华大学" in names and "国家大学生就业服务平台" in names
        assert all(s["consulted_on"] == "2026-10-13" for s in sources)
        assert all(s["url"].startswith("https://") for s in sources)

    def test_optimize_for_job_reports_keyword_gaps(self, api_client):
        resume = _create_resume(api_client)
        use_fake_client(
            [
                {
                    "weak_points": [
                        {
                            "text": "使用 React 与 TypeScript 重构管理后台，页面加载明显更快",
                            "reason": "缺少具体量化结果与场景背景",
                            "question": "这次重构覆盖了哪些页面？加载时间前后对比大概是多少？",
                        },
                        {"text": "这句话不在简历里", "reason": "伪造引用", "question": "不存在"},
                    ],
                    "restructure_advice": "可按 STAR 结构补充：当时的背景、你的任务、采取的行动与可验证的结果。",
                }
            ]
        )
        response = api_client.post(
            f"/api/v1/resumes/{resume['id']}/optimize-for-job",
            json={
                "jd_text": "岗位职责：负责 AI 产品的前端开发，精通 React 与 TypeScript，熟悉 Webpack 构建优化。3 年以上前端经验。",
                "position": "AI全栈工程师",
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        gaps = [g["skill"] for g in body["keyword_gaps"]]
        assert "Webpack" in gaps
        # 伪造引用被服务端剔除，只保留真正来自简历原文的条目
        assert len(body["weak_points"]) == 1
        assert body["weak_points"][0]["question"]
        assert "STAR" in body["restructure_advice"] or "结构" in body["restructure_advice"]
        assert body["model_name"] == "fake-model-test"

    def test_optimize_requires_jd(self, api_client):
        resume = _create_resume(api_client)
        use_fake_client([])
        response = api_client.post(
            f"/api/v1/resumes/{resume['id']}/optimize-for-job", json={"jd_text": "太短"}
        )
        assert response.status_code == 422

    def test_optimize_with_analysis_input(self, api_client):
        use_fake_client([_valid_analysis_payload()])
        analysis = api_client.post(
            "/api/v1/jobs/analyze", json={"jd_text": "岗位名称：AI全栈工程师。负责 AI 产品功能的前端界面与后端服务的设计与实现。要求精通 React 与 TypeScript。"}
        ).json()
        resume = _create_resume(api_client)
        use_fake_client(
            [
                {
                    "weak_points": [],
                    "restructure_advice": "用 STAR 结构组织项目描述。",
                }
            ]
        )
        response = api_client.post(
            f"/api/v1/resumes/{resume['id']}/optimize-for-job",
            json={"job_analysis_id": analysis["id"]},
        )
        assert response.status_code == 200, response.text
        assert response.json()["position"] == "AI全栈工程师"

    def test_optimize_analysis_ownership(self, api_client, db_session):
        use_fake_client([_valid_analysis_payload()])
        analysis = api_client.post(
            "/api/v1/jobs/analyze", json={"jd_text": "岗位名称：AI全栈工程师。负责 AI 产品功能的前端界面与后端服务的设计与实现。要求精通 React 与 TypeScript。"}
        ).json()
        resume = _create_resume(api_client)
        other = _other_user_client(db_session)
        response = other.post(
            f"/api/v1/resumes/{resume['id']}/optimize-for-job",
            json={"job_analysis_id": analysis["id"]},
        )
        # 其他用户的分析不可用 → 404（简历本身也不属于该用户，先触发简历 404 也可）
        assert response.status_code in (404, 409)
