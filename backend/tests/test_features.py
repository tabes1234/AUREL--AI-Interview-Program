"""T2 RAG / T3 技能图谱 / T9 简历匹配 的单元与集成测试。"""

import io
import zipfile

import pytest
from sqlalchemy import select

from app.models import InterviewReport, InterviewTask, User
from app.services import knowledge_service, matching_service
from app.services.retrieval import BM25Index, tokenize

from .conftest import (
    DEFAULT_USER_NICKNAME,
    DEFAULT_USER_USERNAME,
    NO_FOLLOW_UP,
    VALID_SCORING,
    VALID_TASK,
    make_user,
    question_generation_response,
    use_fake_client,
)

# ---------- T2：检索内核 ----------


def test_tokenize_mixed_language():
    tokens = tokenize("前端 React 经验")
    assert "react" in tokens
    assert "前端" in tokens  # bigram
    assert "前" in tokens and "端" in tokens  # 单字


def test_bm25_ranks_relevant_chunk_first():
    docs = {
        1: "React 组件的状态管理使用 useState 与 useReducer。",
        2: "Python 的装饰器是一种语法糖。",
        3: "数据库索引可以加速查询，但会增加写入开销。",
    }
    index = BM25Index(docs)
    hits = index.search("React 状态管理", top_k=2)
    assert hits[0].key == 1
    assert hits[0].score > 0


def test_bm25_empty_index_returns_nothing():
    index = BM25Index({})
    assert index.search("任何查询") == []


# ---------- T2：文档提取与分块 ----------


def _make_docx(paragraphs: list[str]) -> bytes:
    w_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = "".join(
        f'<w:p><w:r><w:t>{p}</w:t></w:r></w:p>' for p in paragraphs
    )
    xml = (
        '<?xml version="1.0"?>'
        f'<w:document xmlns:w="{w_ns}"><w:body>{body}</w:body></w:document>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


def test_extract_text_txt_utf8_and_gb18030():
    assert knowledge_service.extract_text("a.txt", "前端知识".encode("utf-8")) == "前端知识"
    assert knowledge_service.extract_text("b.md", "数据库索引".encode("gb18030")) == "数据库索引"


def test_extract_text_docx():
    data = _make_docx(["第一段：React 状态管理", "第二段：useReducer 用法"])
    text = knowledge_service.extract_text("notes.docx", data)
    assert "React 状态管理" in text
    assert "useReducer 用法" in text


def test_extract_text_unsupported_suffix():
    with pytest.raises(knowledge_service.DocumentError):
        knowledge_service.extract_text("a.pdf", b"whatever")


def test_extract_text_corrupted_docx():
    with pytest.raises(knowledge_service.DocumentError):
        knowledge_service.extract_text("bad.docx", b"not a zip")


def test_chunk_text_merges_and_splits():
    text = "\n\n".join(f"段落{i}：" + "内容" * 80 for i in range(5))
    chunks = knowledge_service.chunk_text(text)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk) <= 1100  # 目标 500 字 + 余量
    assert "".join(chunks).startswith("段落0")


def test_create_document_and_retrieve(db_session):
    owner = make_user(db_session, username="doc-owner", nickname="文档用户")
    document = knowledge_service.create_document(
        db_session,
        title="前端面试笔记",
        filename="notes.md",
        text="React 的受控组件将表单值交给 state 管理。\n\n" + "受控组件的每次输入都会触发状态更新。状态提升让多个组件共享数据。\n\n" * 20
    + "装饰器是 Python 的语法糖。",
        user_id=owner.id,
    )
    assert len(document.chunks) >= 2
    evidence = knowledge_service.retrieve_from_document(
        document, query="React 受控组件", top_k=1
    )
    assert evidence
    assert "受控组件" in evidence[0]


def test_retrieve_evidence_traces_source(db_session):
    owner = make_user(db_session, username="doc-owner", nickname="文档用户")
    knowledge_service.create_document(
        db_session, title="数据库笔记", filename="db.md", text="索引可以加速查询。",
        user_id=owner.id,
    )
    knowledge_service.create_document(
        db_session, title="前端笔记", filename="fe.md", text="虚拟 DOM 减少重绘。",
        user_id=owner.id,
    )
    evidence = knowledge_service.retrieve_evidence(
        db_session, "索引 加速 查询", top_k=1, user_id=owner.id
    )
    assert len(evidence) == 1
    assert evidence[0].document_title == "数据库笔记"
    assert evidence[0].score > 0


# ---------- T2：API 集成 ----------


def test_upload_list_delete_document(api_client):
    paragraph = "受控组件的每次输入都会触发状态更新，状态提升让多个组件共享同一份数据。"
    content = (
        "React 状态管理笔记：useState 是最基础的 Hook，适合简单状态。\n\n"
        + (paragraph + "\n\n") * 6
        + "useReducer 适合复杂状态机，配合 Context 可以替代部分 Redux 场景。\n\n"
        + (paragraph + "\n\n") * 6
        + "性能优化常用 useMemo 与 useCallback 减少不必要的重渲染。"
    ).encode()
    response = api_client.post(
        "/api/v1/knowledge/documents",
        files={"file": ("react.md", content, "text/markdown")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["chunk_count"] >= 2
    assert body["title"] == "react"

    listed = api_client.get("/api/v1/knowledge/documents")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    detail = api_client.get(f"/api/v1/knowledge/documents/{body['id']}")
    assert detail.status_code == 200
    assert detail.json()["chunks"]

    deleted = api_client.delete(f"/api/v1/knowledge/documents/{body['id']}")
    assert deleted.status_code == 204
    assert api_client.get(f"/api/v1/knowledge/documents/{body['id']}").status_code == 404


def test_upload_rejects_unsupported_format(api_client):
    # .pdf 已受支持（纯文本提取）；此处使用真正不支持的扩展名验证格式拦截
    response = api_client.post(
        "/api/v1/knowledge/documents",
        files={"file": ("resume.exe", b"MZ" + b"\x00" * 32, "application/octet-stream")},
    )
    assert response.status_code == 422
    assert "格式" in response.json()["detail"]


def test_upload_rejects_empty_file(api_client):
    response = api_client.post(
        "/api/v1/knowledge/documents",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert response.status_code == 422


def test_search_returns_scored_evidence(api_client):
    api_client.post(
        "/api/v1/knowledge/documents",
        files={"file": ("db.md", "Redis 缓存可以显著降低数据库压力。".encode(), "text/plain")},
    )
    response = api_client.get("/api/v1/knowledge/search", params={"q": "Redis 缓存"})
    assert response.status_code == 200
    body = response.json()
    assert body["evidence"]
    assert body["evidence"][0]["score"] > 0
    assert body["evidence"][0]["document_title"] == "db"  # 标题取文件名去扩展名


def test_create_task_with_knowledge_document_injects_evidence(api_client):
    upload = api_client.post(
        "/api/v1/knowledge/documents",
        files={"file": ("notes.md", "高频考点：React 受控组件与非受控组件的差异。".encode(), "text/plain")},
    )
    document_id = upload.json()["id"]
    fake = use_fake_client([question_generation_response(3), NO_FOLLOW_UP, NO_FOLLOW_UP, NO_FOLLOW_UP])

    response = api_client.post(
        "/api/v1/interviews", json={**VALID_TASK, "knowledge_document_id": document_id}
    )
    assert response.status_code == 201
    system, user = fake.calls[0]
    assert "用户知识库" in user
    assert "受控组件" in user


def test_create_task_with_missing_document_returns_404(api_client):
    use_fake_client([question_generation_response(3)])
    response = api_client.post(
        "/api/v1/interviews", json={**VALID_TASK, "knowledge_document_id": 9999}
    )
    assert response.status_code == 404


# ---------- T3：技能画像 / 图谱 / 自适应训练 ----------


def _seed_reports(db_session, scores: list[float]) -> None:
    user = db_session.scalar(select(User).where(User.username == DEFAULT_USER_USERNAME))
    if user is None:
        user = User(
            username=DEFAULT_USER_USERNAME,
            nickname=DEFAULT_USER_NICKNAME,
            password_hash="pbkdf2_sha256$240000$test$stub",
        )
        db_session.add(user)
        db_session.flush()
    for i, overall in enumerate(scores):
        task = InterviewTask(
            position="前端工程师",
            description="",
            difficulty="intermediate",
            language="zh",
            question_count=3,
            status="completed",
            user_id=user.id,
        )
        db_session.add(task)
        db_session.flush()
        db_session.add(
            InterviewReport(
                task_id=task.id,
                overall_score=overall,
                summary="summary",
                dimensions=[
                    {"name": "内容深度", "score": overall - 2, "evidence": "e", "rationale": "r"},
                    {"name": "表达清晰", "score": overall + 2, "evidence": "e", "rationale": "r"},
                    {"name": "逻辑结构", "score": overall, "evidence": "e", "rationale": "r"},
                    {"name": "岗位匹配", "score": overall - 1, "evidence": "e", "rationale": "r"},
                ],
                strengths=["s"],
                improvements=[{"title": "t", "detail": "d"}],
                model_name="test-model",
            )
        )
    db_session.commit()


def test_skill_profile_empty(api_client):
    profile = api_client.get("/api/v1/skills/profile").json()
    assert profile["has_data"] is False
    graph = api_client.get("/api/v1/skills/graph").json()
    assert graph["available"] is False
    rec = api_client.get("/api/v1/skills/recommendation").json()
    assert rec["available"] is False


def test_skill_profile_aggregates_real_history(api_client, db_session):
    _seed_reports(db_session, [70.0, 80.0])
    profile = api_client.get("/api/v1/skills/profile").json()
    assert profile["has_data"] is True
    assert profile["completed_interviews"] == 2
    assert profile["average_score"] == 75.0
    assert profile["latest_score"] == 80.0
    assert "内容深度" in profile["dimension_averages"]
    assert profile["positions_practiced"] == ["前端工程师"]


def test_training_recommendation_driven_by_weakest_dimension(api_client, db_session):
    _seed_reports(db_session, [60.0, 62.0])
    rec = api_client.get("/api/v1/skills/recommendation").json()
    assert rec["available"] is True
    # 内容深度每场都比其他维度低 2 分，应为最弱
    assert rec["weakest_dimension"] == "内容深度"
    assert rec["suggested_difficulty"] == "basic"
    assert rec["focus_hint"]
    assert rec["based_on"]["completed_interviews"] == 2


def test_training_recommendation_upgrades_difficulty_on_high_scores(api_client, db_session):
    _seed_reports(db_session, [85.0, 88.0])
    rec = api_client.get("/api/v1/skills/recommendation").json()
    assert rec["suggested_difficulty"] == "advanced"


def test_skill_graph_returns_nodes_and_history(api_client, db_session):
    _seed_reports(db_session, [70.0, 80.0])
    graph = api_client.get("/api/v1/skills/graph").json()
    assert graph["available"] is True
    assert len(graph["nodes"]) == 4
    assert graph["nodes"][0]["name"] == "内容深度"
    assert len(graph["score_history"]) == 2
    assert graph["average_score"] == 75.0


# ---------- T9：简历匹配 ----------


def test_extract_matched_skills_with_evidence():
    resume = "三年 React 开发经验，熟悉 TypeScript。\n\n使用 MySQL 做过数据存储。"
    job = "岗位要求：熟悉 React 与 TypeScript，了解 MySQL，有 Docker 部署经验。"
    matched, missing = matching_service.extract_matched_skills(resume, job)
    names = [m["skill"] for m in matched]
    assert "React" in names and "TypeScript" in names and "MySQL" in names
    react = next(m for m in matched if m["skill"] == "React")
    assert react["evidence"] and "React" in react["evidence"]
    assert react["job_evidence"] and "React" in react["job_evidence"]
    assert "Docker" in missing  # 岗位要求但简历缺失


def test_skill_boundary_java_vs_javascript():
    resume = "精通 JavaScript 与浏览器调试"
    job = "需要扎实的 Java 后端功底与前端 JavaScript 能力"
    matched, missing = matching_service.extract_matched_skills(resume, job)
    names = [m["skill"] for m in matched]
    assert "JavaScript" in names
    assert "Java" not in names  # 词边界：简历只有 JavaScript，不应误命中 Java
    assert "Java" in missing


def test_compute_match_score_range():
    score = matching_service.compute_match_score("React 经验", "要求 React", 3, 1)
    assert 0.0 <= score <= 100.0


def test_match_resume_llm_failure_degrades_gracefully():
    class FailingClient:
        model = "fake-model"

        def chat_json(self, system: str, user: str, *, temperature: float = 0.3,
                      service: str = "unattributed") -> dict:
            from app.services.ark_client import ArkError

            raise ArkError("模拟网络故障")

    result = matching_service.match_resume(
        None,
        FailingClient(),
        position="前端工程师",
        job_description="要求 React 与 TypeScript",
        resume_text="三年 React 与 TypeScript 开发经验，负责核心模块。",
    )
    assert result.match_score > 0
    assert result.matched_skills
    assert result.suggestions == []
    assert result.llm_error == "模拟网络故障"


def test_match_resume_api_end_to_end(api_client):
    fake = use_fake_client(
        [{"suggestions": ["补充 Docker 容器化经验", "补充单元测试实践", "准备项目亮点陈述"]}]
    )
    response = api_client.post(
        "/api/v1/matching/resume",
        json={
            "position": "前端工程师",
            "job_description": "要求熟悉 React、TypeScript，了解 Docker 部署",
            "resume_text": "五年前端开发经验，主导过 React 中后台系统，熟练使用 TypeScript。",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["match_score"] > 0
    assert {m["skill"] for m in body["matched_skills"]} >= {"React", "TypeScript"}
    assert "Docker" in body["missing_skills"]
    assert len(body["suggestions"]) == 3
    assert body["model_name"] == "fake-model-test"

    records = api_client.get("/api/v1/matching/records").json()
    assert len(records) == 1
    detail = api_client.get(f"/api/v1/matching/records/{records[0]['id']}").json()
    assert detail["position"] == "前端工程师"
    assert detail["result"]["match_score"] == body["match_score"]

    deleted = api_client.delete(f"/api/v1/matching/records/{records[0]['id']}")
    assert deleted.status_code == 204
    assert api_client.get("/api/v1/matching/records").json() == []


def test_match_resume_api_validation(api_client):
    use_fake_client([])
    response = api_client.post(
        "/api/v1/matching/resume",
        json={"position": "前端工程师", "job_description": "", "resume_text": "太短"},
    )
    assert response.status_code == 422


def test_match_record_404(api_client):
    assert api_client.get("/api/v1/matching/records/999").status_code == 404
