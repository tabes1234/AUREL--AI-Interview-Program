"""回澜错题本：请求 / 响应模型（SM-2 间隔重复调度）。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models import MistakeCard, utcnow


class MistakeCollect(BaseModel):
    question_id: int
    # 用户可粘贴当时的回答；留空则只收题目本身
    my_answer: str = Field(default="", max_length=8000)


class MistakeReview(BaseModel):
    # SM-2 质量分：0=完全想不起 3=勉强想起 4=想起 5=轻松想起（前端映射四键）
    grade: int = Field(ge=0, le=5)


class MistakeCardOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question_id: int
    position: str
    question_content: str
    category: str | None
    dimension: str | None
    goal: str | None
    rubric: list | None
    my_answer: str
    repetitions: int
    ease_factor: float
    interval_days: int
    due_at: datetime
    last_grade: int | None
    last_reviewed_at: datetime | None
    review_count: int
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_due(self) -> bool:
        return self.due_at <= utcnow()


def mistake_out(card: MistakeCard) -> MistakeCardOut:
    return MistakeCardOut.model_validate(card, from_attributes=True)


class MistakeListResponse(BaseModel):
    total: int
    due_count: int
    cards: list[MistakeCardOut]
