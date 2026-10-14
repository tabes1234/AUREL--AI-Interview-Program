"""知途（AI 职业顾问「小鸥」）对话的请求/响应模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=60)

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    created_at: datetime


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = []


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def _strip_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("消息内容不能为空")
        return value


class MessagePairOut(BaseModel):
    """一次完整问答：用户消息 + 小鸥的回复（AI 失败时整对不落库）。"""

    user_message: MessageOut
    assistant_message: MessageOut
    model_name: str | None = None


class ConversationUpdate(BaseModel):
    """重命名会话（自动生成的标题允许用户编辑）。"""

    title: str = Field(min_length=1, max_length=60)

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("标题不能为空")
        return value


FACT_CATEGORY_SET = {
    "stage", "major", "skill", "experience", "industry", "target_role",
    "difficulty", "constraint", "achievement", "goal", "other",
}
FACT_SOURCE_LABELS = {
    "user_stated": "我提供的事实",
    "ai_generalized": "AI 归纳 · 待确认",
    "ai_inferred": "AI 推断",
}


class ProfileFactCreate(BaseModel):
    """用户主动补充一条自己的档案事实（视为已确认）。"""

    category: str = "other"
    content: str = Field(min_length=1, max_length=300)

    @field_validator("category")
    @classmethod
    def _check_category(cls, value: str) -> str:
        if value not in FACT_CATEGORY_SET:
            raise ValueError("未知的档案类别")
        return value

    @field_validator("content")
    @classmethod
    def _strip_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("内容不能为空")
        return value


class ProfileFactUpdate(BaseModel):
    """编辑/确认某条档案事实（仅本人可见可改）。"""

    content: str | None = Field(default=None, min_length=1, max_length=300)
    category: str | None = None
    confirmed: bool | None = None

    @field_validator("content")
    @classmethod
    def _strip_content(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("内容不能为空")
        return value

    @field_validator("category")
    @classmethod
    def _check_category(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in FACT_CATEGORY_SET:
            raise ValueError("未知的档案类别")
        return value


class ProfileFactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category: str
    content: str
    source_type: str
    source_message_id: int | None = None
    confidence: str | None = None
    quote: str | None = None
    confirmed: bool
    created_at: datetime
    updated_at: datetime


class ProfileOut(BaseModel):
    """长期职业档案：AI 总结 + 全部事实（含未确认，前端明确区分展示）。"""

    summary: str | None = None
    facts: list[ProfileFactOut] = []
    confirmed_count: int = 0
    pending_count: int = 0


class ProfileOrganizeRequest(BaseModel):
    conversation_id: int | None = None


class PlanActionCreate(BaseModel):
    phase: str = "30d"
    goal: str = Field(min_length=1, max_length=200)
    steps: str | None = Field(default=None, max_length=1000)
    related_goal: str | None = Field(default=None, max_length=200)

    @field_validator("phase")
    @classmethod
    def _check_phase(cls, value: str) -> str:
        if value not in {"7d", "30d", "90d"}:
            raise ValueError("阶段只能是 7d / 30d / 90d")
        return value


class PlanActionUpdate(BaseModel):
    status: str | None = None
    review: str | None = Field(default=None, max_length=1000)
    goal: str | None = Field(default=None, min_length=1, max_length=200)
    steps: str | None = Field(default=None, max_length=1000)
    related_goal: str | None = Field(default=None, max_length=200)
    due_at: datetime | None = None

    @field_validator("status")
    @classmethod
    def _check_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in {"pending", "done", "skipped"}:
            raise ValueError("任务状态只能是 pending / done / skipped")
        return value


class PlanActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    phase: str
    goal: str
    steps: str
    due_at: datetime | None = None
    status: str
    review: str | None = None
    related_goal: str | None = None
    position: int
    completed_at: datetime | None = None


class PlanGenerateRequest(BaseModel):
    conversation_id: int | None = None
    job_analysis_id: int | None = None
    goal: str | None = Field(default=None, max_length=120)


class PlanUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    status: str | None = None

    @field_validator("status")
    @classmethod
    def _check_status(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in {"active", "archived"}:
            raise ValueError("计划状态只能是 active / archived")
        return value


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    situation: str
    focus_role: str | None = None
    status: str
    version_no: int
    conversation_id: int | None = None
    created_at: datetime
    updated_at: datetime
    actions: list[PlanActionOut] = []


class PlanSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    focus_role: str | None = None
    status: str
    version_no: int
    created_at: datetime
    updated_at: datetime
    pending_count: int = 0
    done_count: int = 0
    skipped_count: int = 0


class WorkflowCreate(BaseModel):
    kind: str
    params: dict = {}

    @field_validator("kind")
    @classmethod
    def _check_kind(cls, value: str) -> str:
        if value not in {"gap_analysis", "interview_prep"}:
            raise ValueError("未知的工作流类型")
        return value


class WorkflowStepOut(BaseModel):
    key: str
    title: str
    status: str
    detail: str | None = None


class WorkflowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    status: str
    params: dict = {}
    steps: list[WorkflowStepOut] = []
    result: dict | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
