"""度衡：限时模拟挑战的请求 / 响应模型。"""

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models import ChallengeRun, utcnow

DIFFICULTIES = ("basic", "intermediate", "advanced")


class ChallengeCreate(BaseModel):
    position: str = Field(min_length=2, max_length=60)
    difficulty: Literal["basic", "intermediate", "advanced"] = "intermediate"
    question_count: int = Field(default=5, ge=3, le=8)
    duration_minutes: int = Field(default=15, ge=5, le=60)


class ChallengeSubmit(BaseModel):
    answers: list[dict] = Field(min_length=1, max_length=12)


class ChallengeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    position: str
    difficulty: str
    language: str
    question_count: int
    duration_minutes: int
    status: str
    questions: list[dict]
    answers: list[dict] | None
    started_at: datetime | None
    deadline_at: datetime | None
    submitted_at: datetime | None
    overtime: bool
    overall_score: float | None
    result: dict | None
    model_name: str | None
    error_message: str | None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def remaining_seconds(self) -> int | None:
        """进行中挑战的剩余秒数（服务端时钟）；非进行中返回 None。"""
        if self.status != "in_progress" or self.deadline_at is None:
            return None
        deadline = self.deadline_at.replace(tzinfo=timezone.utc)
        remaining = (deadline - datetime.now(timezone.utc)).total_seconds()
        return max(0, int(remaining))


def challenge_out(run: ChallengeRun) -> ChallengeOut:
    return ChallengeOut.model_validate(run, from_attributes=True)


# ---------- AI 出题结构化校验 ----------


class ChallengeAiQuestion(BaseModel):
    order_index: int = Field(ge=1, le=12)
    content: str = Field(min_length=5, max_length=800)
    category: str = Field(default="综合", max_length=30)
    dimension: str = Field(default="", max_length=60)
    rubric: list[str] = Field(default_factory=list, max_length=8)


class ChallengeAiQuestionSet(BaseModel):
    questions: list[ChallengeAiQuestion] = Field(min_length=3, max_length=8)
