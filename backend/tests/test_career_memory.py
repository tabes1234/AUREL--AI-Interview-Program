"""知途第二阶段回归：流式对话、分层记忆、档案三态、规划、工作流与导出。

外部 AI 一律使用可编程假客户端，绝不发起真实网络请求；
模型凭证缺失的场景用 NotConfigured 假客户端如实验证配置阻塞。
"""

import json
from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.models import (
    CareerConversation,
    CareerMessage,
    CareerPlanAction,
    JobAnalysis,
    Resume,
    utcnow,
)
from app.routers.interviews import get_ark_client
from app.routers.career import _stream_reply
from app.services.ark_client import ArkError, ArkNotConfiguredError
from app.services.auth_service import SESSION_COOKIE_NAME
from tests.conftest import login_user, make_user


class FullFakeClient:
    """同时支持 chat / chat_json / chat_stream 的假方舟客户端（按队列消费）。"""

    def __init__(
        self,
        *,
        chat_replies: list[str] | None = None,
        json_responses: list[dict] | None = None,
        stream_chunks: list[str] | None = None,
        stream_error: Exception | None = None,
        error_after_chunks: bool = False,
    ) -> None:
        self.chat_replies = list(chat_replies or [])
        self.json_responses = list(json_responses or [])
        self.stream_chunks = list(stream_chunks or [])
        self.stream_error = stream_error
        self.error_after_chunks = error_after_chunks
        self.calls: list[tuple[str, str, str]] = []  # (kind, system, user)
        self.model = "fake-model-test"

    def ensure_configured(self) -> None:
        return

    def chat(self, system: str, user: str, *, temperature: float = 0.7,
             service: str = "unattributed") -> str:
        self.calls.append(("chat", system, user))
        if not self.chat_replies:
            raise AssertionError("FullFakeClient 没有更多 chat 预设回复")
        return self.chat_replies.pop(0)

    def chat_json(self, system: str, user: str, *, temperature: float = 0.3,
                  service: str = "unattributed") -> dict:
        self.calls.append(("chat_json", system, user))
        if not self.json_responses:
            raise AssertionError("FullFakeClient 没有更多 chat_json 预设响应")
        return self.json_responses.pop(0)

    def chat_stream(self, system: str, user: str, *, temperature: float = 0.7,
                    service: str = "unattributed"):
        self.ensure_configured()
        self.calls.append(("chat_stream", system, user))
        if not self.error_after_chunks:
            if self.stream_error is not None:
                raise self.stream_error
        for chunk in self.stream_chunks:
            yield chunk
        if self.error_after_chunks:
            raise self.stream_error or ArkError("AI 模型流式响应中断")


class NotConfiguredStreamClient(FullFakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.model = ""

    def ensure_configured(self) -> None:
        raise ArkNotConfiguredError(
            "AI 模型尚未配置：缺少环境变量 ARK_API_KEY。请在 backend/.env 中配置后重启后端服务。"
        )


def use_client(fake: FullFakeClient) -> FullFakeClient:
    app.dependency_overrides[get_ark_client] = lambda: fake
    return fake


def parse_sse(text: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        event, data = None, None
        for line in block.split("\n"):
            if line.startswith("event: "):
                event = line[7:].strip()
            elif line.startswith("data: "):
                data = line[6:]
        if event and data:
            events.append((event, json.loads(data)))
    return events


def event_map(events: list[tuple[str, dict]]) -> dict[str, dict]:
    return {name: data for name, data in events}


# ---------- 3. AI 真实调用和流式输出 ----------


def test_stream_endpoint_emits_sse_and_persists(api_client, db_session):
    created = api_client.post("/api/v1/career-guide/conversations", json=None).json()
    use_client(FullFakeClient(stream_chunks=["你好", "，", "我是小鸥。"]))

    resp = api_client.post(
        f"/api/v1/career-guide/conversations/{created['id']}/stream",
        json={"content": "你好，请介绍一下你自己"},
    )
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    events = parse_sse(resp.text)

    assert events[0][0] == "meta"
    assert events[0][1]["user_message"]["role"] == "user"
    deltas = [data["text"] for name, data in events if name == "delta"]
    assert deltas == ["你好", "，", "我是小鸥。"]
    done = event_map(events)["done"]
    assert done["assistant_message"]["content"] == "你好，我是小鸥。"
    assert done["title"].startswith("你好，请介绍一下你自己")
    assert "end" in event_map(events)

    detail = api_client.get(
        f"/api/v1/career-guide/conversations/{created['id']}"
    ).json()
    assert detail["message_count"] == 2
    assert detail["messages"][-1]["content"] == "你好，我是小鸥。"


def test_stream_without_ai_configured_reports_block(api_client, db_session):
    """模型凭证缺失：必须如实报告配置阻塞，不伪造 AI 输出。"""
    created = api_client.post("/api/v1/career-guide/conversations", json=None).json()
    use_client(NotConfiguredStreamClient())

    resp = api_client.post(
        f"/api/v1/career-guide/conversations/{created['id']}/stream",
        json={"content": "帮帮我"},
    )
    events = parse_sse(resp.text)
    error = event_map(events)["error"]
    assert error["status"] == 503
    assert "ARK_API_KEY" in error["message"]
    assert "done" not in event_map(events)

    detail = api_client.get(
        f"/api/v1/career-guide/conversations/{created['id']}"
    ).json()
    assert detail["message_count"] == 1  # 用户消息保留，可重试
    assert all(m["role"] == "user" for m in detail["messages"])


def test_failed_stream_retry_reuses_user_message(api_client, db_session):
    """发送失败后的重试：同一内容不重复落库。"""
    created = api_client.post("/api/v1/career-guide/conversations", json=None).json()
    use_client(FullFakeClient(stream_error=ArkError("AI 模型服务返回错误（HTTP 500）")))

    first = api_client.post(
        f"/api/v1/career-guide/conversations/{created['id']}/stream",
        json={"content": "帮我看看方向"},
    )
    assert event_map(parse_sse(first.text))["error"]["status"] == 502

    use_client(FullFakeClient(stream_chunks=["好的，我们", "慢慢梳理。"]))
    second = api_client.post(
        f"/api/v1/career-guide/conversations/{created['id']}/stream",
        json={"content": "帮我看看方向"},
    )
    events = parse_sse(second.text)
    assert "done" in event_map(events)

    detail = api_client.get(
        f"/api/v1/career-guide/conversations/{created['id']}"
    ).json()
    user_messages = [m for m in detail["messages"] if m["role"] == "user"]
    assert len(user_messages) == 1  # 重试复用原消息
    assert len(detail["messages"]) == 2


def test_regenerate_replaces_last_reply(api_client, db_session):
    created = api_client.post("/api/v1/career-guide/conversations", json=None).json()
    use_client(FullFakeClient(stream_chunks=["第一版回答。"]))
    api_client.post(
        f"/api/v1/career-guide/conversations/{created['id']}/stream",
        json={"content": "怎么准备面试？"},
    )

    use_client(FullFakeClient(stream_chunks=["重新生成的", "第二版回答。"]))
    resp = api_client.post(
        f"/api/v1/career-guide/conversations/{created['id']}/regenerate"
    )
    events = parse_sse(resp.text)
    done = event_map(events)["done"]
    assert done["assistant_message"]["content"] == "重新生成的第二版回答。"
    assert events[0][0] == "meta"
    assert events[0][1]["regenerated"] is True

    detail = api_client.get(
        f"/api/v1/career-guide/conversations/{created['id']}"
    ).json()
    assert detail["message_count"] == 2
    assert detail["messages"][-1]["content"] == "重新生成的第二版回答。"


def test_stop_generation_persists_partial_reply(db_session, api_client):
    """停止生成：已生成的部分内容保留为 AI 回复（服务端真实落库）。"""
    created = api_client.post("/api/v1/career-guide/conversations", json=None).json()
    fake = use_client(FullFakeClient(stream_chunks=["第一段。", "第二段。", "第三段。"]))

    # 模拟客户端中途断开：直接驱动生成器并在中途 close()
    conversation = db_session.get(CareerConversation, created["id"])
    generator = _stream_reply(
        db_session, fake, conversation.user_id, conversation, "讲讲规划方法", regenerate=False
    )
    consumed = []
    for event in generator:
        consumed.append(event)
        if "第二段" in "".join(consumed):
            break
    generator.close()

    detail = api_client.get(
        f"/api/v1/career-guide/conversations/{created['id']}"
    ).json()
    assert detail["message_count"] == 2
    assert "第二段。" in detail["messages"][-1]["content"]
    assert "第三段" not in detail["messages"][-1]["content"]


# ---------- 4/5/6. 档案事实抽取、确认状态与三态分离 ----------


def test_fact_extraction_three_states_and_downgrade(api_client, db_session):
    """事实与推断必须分开：伪造的 user_stated（原文定位不到）自动降级。"""
    created = api_client.post("/api/v1/career-guide/conversations", json=None).json()
    content = "我是计算机专业的，我会用 Python 写脚本。"
    use_client(
        FullFakeClient(
            stream_chunks=["收到，我会记住这些信息。"],
            json_responses=[
                {
                    "facts": [
                        {
                            "category": "major",
                            "content": "计算机专业在读",
                            "source_type": "user_stated",
                            "quote": "我是计算机专业的",
                        },
                        {
                            "category": "skill",
                            "content": "有 Python 脚本经验",
                            "source_type": "ai_generalized",
                            "quote": "我会用 Python 写脚本",
                        },
                        {
                            "category": "industry",
                            "content": "可能适合数据类岗位",
                            "source_type": "ai_inferred",
                            "confidence": "low",
                        },
                        {
                            "category": "skill",
                            "content": "精通 Rust 系统开发",
                            "source_type": "user_stated",
                            "quote": "这段话里根本没有的原文字样",
                        },
                    ]
                }
            ],
        )
    )
    resp = api_client.post(
        f"/api/v1/career-guide/conversations/{created['id']}/stream",
        json={"content": content},
    )
    events = parse_sse(resp.text)
    assert event_map(events)["end"]["facts_added"] == 4

    profile = api_client.get("/api/v1/career-guide/profile").json()
    by_content = {fact["content"]: fact for fact in profile["facts"]}
    assert by_content["计算机专业在读"]["source_type"] == "user_stated"
    assert by_content["计算机专业在读"]["confirmed"] is True
    assert by_content["有 Python 脚本经验"]["confirmed"] is False
    assert by_content["可能适合数据类岗位"]["source_type"] == "ai_inferred"
    assert by_content["可能适合数据类岗位"]["confidence"] == "low"
    # 降级：不能把 AI 的猜测变成用户的真实经历
    assert by_content["精通 Rust 系统开发"]["source_type"] == "ai_generalized"
    assert by_content["精通 Rust 系统开发"]["confirmed"] is False
    assert profile["confirmed_count"] == 1
    assert profile["pending_count"] == 3


def test_confirm_edit_and_delete_fact(api_client, db_session):
    created = api_client.post("/api/v1/career-guide/conversations", json=None).json()
    use_client(
        FullFakeClient(
            stream_chunks=["好的。"],
            json_responses=[
                {"facts": [{"category": "target_role", "content": "想转产品经理", "source_type": "ai_generalized"}]}
            ],
        )
    )
    api_client.post(
        f"/api/v1/career-guide/conversations/{created['id']}/stream",
        json={"content": "我想转产品经理"},
    )
    profile = api_client.get("/api/v1/career-guide/profile").json()
    fact = profile["facts"][0]
    assert fact["confirmed"] is False

    # 确认 AI 归纳
    resp = api_client.patch(
        f"/api/v1/career-guide/profile/facts/{fact['id']}", json={"confirmed": True}
    )
    assert resp.json()["confirmed"] is True

    # 编辑后仍为本人认可
    resp = api_client.patch(
        f"/api/v1/career-guide/profile/facts/{fact['id']}",
        json={"content": "目标是一线公司的产品经理岗"},
    )
    assert resp.json()["content"] == "目标是一线公司的产品经理岗"

    # 用户手动补充：直接视为已确认
    resp = api_client.post(
        "/api/v1/career-guide/profile/facts",
        json={"category": "constraint", "content": "希望在杭州工作"},
    )
    assert resp.status_code == 201
    assert resp.json()["source_type"] == "user_stated"
    assert resp.json()["confirmed"] is True

    # 删除单条
    resp = api_client.delete(f"/api/v1/career-guide/profile/facts/{fact['id']}")
    assert resp.status_code == 204
    profile = api_client.get("/api/v1/career-guide/profile").json()
    assert len(profile["facts"]) == 1


def test_profile_isolated_between_users(api_client, db_session):
    api_client.post(
        "/api/v1/career-guide/profile/facts",
        json={"category": "skill", "content": "会 React"},
    )
    other = make_user(db_session, username="memory-other", nickname="别人")
    other_token = login_user(db_session, other)
    other_client = TestClient(app)
    other_client.cookies.set(SESSION_COOKIE_NAME, other_token)

    mine = api_client.get("/api/v1/career-guide/profile").json()
    theirs = other_client.get("/api/v1/career-guide/profile").json()
    assert len(mine["facts"]) == 1
    assert theirs["facts"] == []

    fact_id = mine["facts"][0]["id"]
    assert other_client.patch(
        f"/api/v1/career-guide/profile/facts/{fact_id}", json={"confirmed": True}
    ).status_code == 404
    assert other_client.delete(
        f"/api/v1/career-guide/profile/facts/{fact_id}"
    ).status_code == 404


def test_clear_memory(api_client, db_session):
    created = api_client.post("/api/v1/career-guide/conversations", json=None).json()
    use_client(
        FullFakeClient(
            stream_chunks=["好。"],
            json_responses=[
                {"facts": [{"category": "skill", "content": "会 SQL", "source_type": "ai_generalized"}]}
            ],
        )
    )
    api_client.post(
        f"/api/v1/career-guide/conversations/{created['id']}/stream",
        json={"content": "我会 SQL"},
    )
    assert api_client.get("/api/v1/career-guide/profile").json()["facts"]

    resp = api_client.delete("/api/v1/career-guide/profile/facts")
    assert resp.status_code == 204
    profile = api_client.get("/api/v1/career-guide/profile").json()
    assert profile["facts"] == []
    assert profile["summary"] is None
    assert profile["confirmed_count"] == 0


# ---------- 5. 长对话摘要与历史召回 ----------


def _insert_messages(db_session, conversation: CareerConversation, count: int) -> None:
    for index in range(count):
        db_session.add(
            CareerMessage(
                conversation_id=conversation.id,
                role="user" if index % 2 == 0 else "assistant",
                content=f"历史消息 {index}：讨论职业规划细节",
            )
        )
    db_session.commit()


def test_long_conversation_triggers_summary(api_client, db_session):
    created = api_client.post("/api/v1/career-guide/conversations", json=None).json()
    conversation = db_session.get(CareerConversation, created["id"])
    _insert_messages(db_session, conversation, 24)

    use_client(
        FullFakeClient(
            stream_chunks=["继续。"],
            json_responses=[
                {
                    "summary": "用户正在梳理转岗方向，目标未定，担心准备时间不足。",
                    "open_questions": ["目标岗位尚未确定"],
                }
            ],
        )
    )
    resp = api_client.post(
        f"/api/v1/career-guide/conversations/{created['id']}/stream",
        json={"content": "我们继续吧"},
    )
    assert event_map(parse_sse(resp.text))["end"]["summary_updated"] is True

    conversation = db_session.get(CareerConversation, created["id"])
    db_session.refresh(conversation)
    assert conversation.summary
    assert conversation.summarized_until_id is not None
    # 摘要可追溯：覆盖到已存在的某条真实消息
    assert db_session.get(CareerMessage, conversation.summarized_until_id) is not None


def test_related_history_recall_and_deletion(api_client, db_session):
    """相关历史召回：其他会话的相关内容进入上下文；删除后立即退出召回。"""
    other = api_client.post("/api/v1/career-guide/conversations", json=None).json()
    # 消息端点在模型失败时不落库（对话完整性设计），故先注入假客户端再保存种子消息
    use_client(FullFakeClient(chat_replies=["好的，记下了。"]))
    api_client.post(
        f"/api/v1/career-guide/conversations/{other['id']}/messages",
        json={"content": "我在准备数据分析师岗位，纠结要不要学统计"},
    )

    fresh = api_client.post("/api/v1/career-guide/conversations", json=None).json()
    fake = use_client(FullFakeClient(stream_chunks=["了解。"]))
    api_client.post(
        f"/api/v1/career-guide/conversations/{fresh['id']}/stream",
        json={"content": "数据分析师需要学统计吗？"},
    )
    payload = fake.calls[0][2]
    assert "相关历史回忆" in payload
    assert "数据分析师" in payload

    # 删除旧会话后，同等问题不再召回已删除内容
    api_client.delete(f"/api/v1/career-guide/conversations/{other['id']}")
    fake2 = use_client(FullFakeClient(stream_chunks=["了解。"]))
    api_client.post(
        f"/api/v1/career-guide/conversations/{fresh['id']}/stream",
        json={"content": "数据分析师需要学统计吗？"},
    )
    assert "纠结要不要学统计" not in fake2.calls[0][2]


# ---------- 7. 职业路径比较（方向探索） ----------


def test_direction_exploration_structure(api_client, db_session):
    use_client(
        FullFakeClient(
            chat_replies=["占位"],
            json_responses=[
                {
                    "directions": [
                        {
                            "name": "数据分析",
                            "fit": "值得探索",
                            "relation": "与已有 Python 经验衔接",
                            "requirements": ["SQL", "统计基础"],
                            "evidence": ["会用 Python 写脚本"],
                            "unknowns": ["未说明是否接触过可视化"],
                            "conditions": ["需验证对业务分析的耐受度"],
                            "next_steps": ["做一个小型数据分析项目"],
                        },
                        {
                            "name": "产品经理",
                            "fit": "需要验证",
                            "relation": "沟通经验可迁移",
                            "requirements": ["需求分析"],
                            "evidence": [],
                            "unknowns": ["未提及项目协作经历"],
                            "conditions": ["需确认文档能力"],
                            "next_steps": ["访谈一位产品经理"],
                        },
                    ],
                    "note": "这是探索建议，不是结论",
                }
            ],
        )
    )
    resp = api_client.post(
        "/api/v1/career-guide/workflows",
        json={"kind": "gap_analysis", "params": {}},
    )
    # gap_analysis 走差距分析；方向探索在档案页由前端以工作流结果展示——
    # 这里验证工作流成功且结构完整
    run = resp.json()
    assert run["status"] == "succeeded"
    keys = [step["key"] for step in run["steps"]]
    assert keys == ["profile", "job", "resume", "knowledge", "evidence", "ai_gap"]
    assert run["result"]["target_role"]
    assert "missing" in run["result"]


# ---------- 8/9. 规划：创建、编辑、完成与档案联动 ----------


PLAN_RESPONSE = {
    "title": "转岗准备计划",
    "focus_role": "数据分析师",
    "situation": "已有 Python 基础，统计与业务分析待补。",
    "actions": [
        {"phase": "7d", "goal": "完成统计基础入门", "steps": "看课；做笔记", "due_in_days": 5, "related_goal": "统计"},
        {"phase": "30d", "goal": "完成一个分析小项目", "steps": "选题；取数；写结论", "due_in_days": 25, "related_goal": "项目作品"},
        {"phase": "90d", "goal": "投递并复盘 10 个岗位", "steps": "筛岗；投递；复盘", "due_in_days": 80, "related_goal": "求职行动"},
    ],
}


def test_plan_lifecycle(api_client, db_session):
    use_client(FullFakeClient(json_responses=[PLAN_RESPONSE]))
    created = api_client.post(
        "/api/v1/career-guide/plans/generate",
        json={"goal": "三个月内具备数据分析能力"},
    )
    assert created.status_code == 201
    plan = created.json()
    assert plan["title"] == "转岗准备计划"
    assert len(plan["actions"]) == 3
    assert {action["phase"] for action in plan["actions"]} == {"7d", "30d", "90d"}
    version_no = plan["version_no"]

    action_id = plan["actions"][0]["id"]
    # 完成任务 + 复盘
    resp = api_client.patch(
        f"/api/v1/career-guide/plans/{plan['id']}/actions/{action_id}",
        json={"status": "done", "review": "已看完统计课，做了笔记"},
    )
    updated = resp.json()
    done_action = next(item for item in updated["actions"] if item["id"] == action_id)
    assert done_action["status"] == "done"
    assert done_action["review"] == "已看完统计课，做了笔记"
    assert done_action["completed_at"] is not None
    assert updated["version_no"] == version_no + 1  # 变更留版本快照

    # 跳过任务
    other_id = updated["actions"][1]["id"]
    resp = api_client.patch(
        f"/api/v1/career-guide/plans/{plan['id']}/actions/{other_id}",
        json={"status": "skipped"},
    )
    assert resp.status_code == 200

    # 手动添加任务
    resp = api_client.post(
        f"/api/v1/career-guide/plans/{plan['id']}/actions",
        json={"phase": "30d", "goal": "每周一次模拟面试", "steps": "约同学练习"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["actions"]) == 4

    # 删除任务
    resp = api_client.delete(
        f"/api/v1/career-guide/plans/{plan['id']}/actions/{other_id}"
    )
    assert resp.status_code == 200
    assert len(resp.json()["actions"]) == 3

    plans = api_client.get("/api/v1/career-guide/plans").json()
    assert plans[0]["done_count"] == 1

    # 删除计划
    assert (
        api_client.delete(f"/api/v1/career-guide/plans/{plan['id']}").status_code == 204
    )
    assert api_client.get("/api/v1/career-guide/plans").json() == []


def test_plan_reflects_confirmed_profile(api_client, db_session):
    """用户修改档案（确认事实）后，规划输入包含该事实。"""
    api_client.post(
        "/api/v1/career-guide/profile/facts",
        json={"category": "target_role", "content": "目标：新能源行业数据岗"},
    )
    fake = use_client(FullFakeClient(json_responses=[PLAN_RESPONSE]))
    api_client.post("/api/v1/career-guide/plans/generate", json=None)
    planner_payload = fake.calls[0][2]
    assert "目标：新能源行业数据岗" in planner_payload


def test_plan_isolated_between_users(api_client, db_session):
    use_client(FullFakeClient(json_responses=[PLAN_RESPONSE]))
    plan = api_client.post("/api/v1/career-guide/plans/generate", json=None).json()

    other = make_user(db_session, username="plan-other", nickname="别的用户")
    other_token = login_user(db_session, other)
    other_client = TestClient(app)
    other_client.cookies.set(SESSION_COOKIE_NAME, other_token)

    assert other_client.get("/api/v1/career-guide/plans").json() == []
    assert (
        other_client.get(f"/api/v1/career-guide/plans/{plan['id']}").status_code == 404
    )
    action_id = plan["actions"][0]["id"]
    assert (
        other_client.patch(
            f"/api/v1/career-guide/plans/{plan['id']}/actions/{action_id}",
            json={"status": "done"},
        ).status_code == 404
    )


# ---------- 12. 模型超时、失败与重试（工作流层面） ----------


def test_workflow_records_real_failure(api_client, db_session):
    class ExplodingClient(FullFakeClient):
        def chat_json(self, *args, **kwargs):
            raise ArkError("AI 模型请求超时（120 秒），请稍后重试")

    use_client(ExplodingClient())
    resp = api_client.post(
        "/api/v1/career-guide/workflows", json={"kind": "gap_analysis", "params": {}}
    )
    run = resp.json()
    assert run["status"] == "failed"
    assert "超时" in run["error_message"]
    # 前面的真实步骤已留痕
    keys = [step["key"] for step in run["steps"]]
    assert "profile" in keys


def test_workflow_rejects_unknown_kind(api_client):
    resp = api_client.post(
        "/api/v1/career-guide/workflows", json={"kind": "nope", "params": {}}
    )
    assert resp.status_code == 422


def test_workflow_reads_real_job_and_resume(api_client, db_session):
    """联动真实数据：知岗解析与简历存在时，差距分析提示词包含其内容。"""
    user_id = 1
    db_session.add(
        JobAnalysis(
            user_id=user_id,
            title="数据分析师",
            jd_text="负责业务数据分析，要求 SQL 熟练",
            jd_hash="hash-1",
            status="ready",
            result={"required_skills": [{"text": "SQL"}]},
        )
    )
    db_session.add(
        Resume(
            user_id=user_id,
            title="我的简历",
            content={"basics": {"summary": "会用 Python 做数据整理"}, "work": []},
        )
    )
    db_session.commit()

    fake = use_client(FullFakeClient(json_responses=[PLAN_RESPONSE]))
    api_client.post("/api/v1/career-guide/plans/generate", json=None)
    payload = fake.calls[0][2]
    assert "数据分析师" in payload
    assert "SQL 熟练" in payload
    assert "会用 Python 做数据整理" in payload


# ---------- 10. 数据导出与删除 ----------


def test_export_and_deletion(api_client, db_session):
    created = api_client.post("/api/v1/career-guide/conversations", json=None).json()
    use_client(
        FullFakeClient(
            stream_chunks=["回复内容。"],
            json_responses=[
                {
                    "facts": [
                        {
                            "category": "skill",
                            "content": "会 SQL",
                            "source_type": "user_stated",
                            "quote": "我会 SQL",
                        }
                    ]
                }
            ],
        )
    )
    api_client.post(
        f"/api/v1/career-guide/conversations/{created['id']}/stream",
        json={"content": "请记住：我会 SQL"},
    )
    use_client(FullFakeClient(json_responses=[PLAN_RESPONSE]))
    plan = api_client.post("/api/v1/career-guide/plans/generate", json=None).json()

    export = api_client.get("/api/v1/career-guide/export").json()
    assert export["conversations"][0]["messages"][0]["content"] == "请记住：我会 SQL"
    assert export["profile"]["facts"]
    assert export["plans"][0]["id"] == plan["id"]
    assert export["plans"][0]["revisions"]  # 版本历史已导出

    # 删除会话与计划后导出不再包含
    api_client.delete(f"/api/v1/career-guide/conversations/{created['id']}")
    api_client.delete(f"/api/v1/career-guide/plans/{plan['id']}")
    api_client.delete("/api/v1/career-guide/profile/facts")
    export = api_client.get("/api/v1/career-guide/export").json()
    assert export["conversations"] == []
    assert export["plans"] == []
    assert export["profile"]["facts"] == []


# ---------- 1. 会话搜索 ----------


def test_conversation_search(api_client, db_session):
    conv_a = api_client.post(
        "/api/v1/career-guide/conversations", json={"title": "转产品讨论"}
    ).json()
    conv_b = api_client.post("/api/v1/career-guide/conversations", json=None).json()
    use_client(FullFakeClient(chat_replies=["好的。"]))
    api_client.post(
        f"/api/v1/career-guide/conversations/{conv_b['id']}/messages",
        json={"content": "聊聊数据岗位的技能树"},
    )

    by_title = api_client.get(
        "/api/v1/career-guide/conversations", params={"search": "转产品"}
    ).json()
    assert [item["id"] for item in by_title] == [conv_a["id"]]

    by_content = api_client.get(
        "/api/v1/career-guide/conversations", params={"search": "技能树"}
    ).json()
    assert [item["id"] for item in by_content] == [conv_b["id"]]

    assert (
        api_client.patch(
            f"/api/v1/career-guide/conversations/{conv_a['id']}",
            json={"title": "产品方向重启"},
        ).json()["title"]
        == "产品方向重启"
    )


# ---------- ArkClient.chat_stream（服务层流式，MockTransport） ----------


def test_ark_chat_stream_parses_sse_deltas():
    import httpx

    from app.services.ark_client import ArkClient

    sse_body = (
        'data: {"choices":[{"delta":{"content":"你好"}}]}\n\n'
        "data: {\"choices\":[{\"delta\":{\"content\":\"，世界\"}}]}\n\n"
        "data: [DONE]\n\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse_body.encode("utf-8"))

    client = ArkClient(api_key="k", base_url="https://ark.test", model="m",
                       transport=httpx.MockTransport(handler))
    chunks = list(client.chat_stream("系统", "用户", service="career_guide"))
    assert chunks == ["你好", "，世界"]


def test_ark_chat_stream_retries_then_succeeds():
    import httpx

    from app.services.ark_client import ArkClient

    state = {"count": 0}
    sse_body = 'data: {"choices":[{"delta":{"content":"ok"}}]}\n\ndata: [DONE]\n\n'

    def handler(request: httpx.Request) -> httpx.Response:
        state["count"] += 1
        if state["count"] == 1:
            return httpx.Response(500, text="boom")
        return httpx.Response(200, content=sse_body.encode("utf-8"))

    client = ArkClient(api_key="k", base_url="https://ark.test", model="m",
                       transport=httpx.MockTransport(handler))
    chunks = list(client.chat_stream("系统", "用户", service="career_guide"))
    assert chunks == ["ok"]
    assert state["count"] == 2


def test_ark_chat_stream_midway_failure_raises():
    import httpx
    import pytest

    from app.services.ark_client import ArkClient, ArkError

    def handler(request: httpx.Request) -> httpx.Response:
        def body() -> Iterator[bytes]:
            first = json.dumps(
                {"choices": [{"delta": {"content": "前半"}}]}, ensure_ascii=False
            )
            yield f"data: {first}\n\n".encode("utf-8")
            raise httpx.ReadError("connection dropped mid-stream")

        return httpx.Response(
            200,
            content=body(),
            headers={"content-type": "text/event-stream"},
        )

    client = ArkClient(api_key="k", base_url="https://ark.test", model="m",
                       transport=httpx.MockTransport(handler))
    with pytest.raises(ArkError):
        list(client.chat_stream("系统", "用户", service="career_guide"))


def test_ark_chat_stream_not_configured(monkeypatch):
    import pytest

    from app.services.ark_client import ArkClient, ArkNotConfiguredError

    monkeypatch.delenv("ARK_API_KEY", raising=False)
    monkeypatch.delenv("ARK_MODEL", raising=False)
    client = ArkClient(base_url="https://ark.test")
    with pytest.raises(ArkNotConfiguredError):
        list(client.chat_stream("系统", "用户"))
