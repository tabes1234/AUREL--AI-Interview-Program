"""洞察新功能：星图对照（观己 × 知岗差距分析）与澜记周报的请求 / 响应模型。"""

from pydantic import BaseModel, ConfigDict, Field


class GapAnalysisRequest(BaseModel):
    job_analysis_id: int = Field(gt=0)


class GapDimensionAi(BaseModel):
    """模型只负责目标值与点评；current 由服务端回填，绝不采信模型给的现值。"""

    name: str = Field(min_length=1, max_length=40)
    target: float = Field(ge=0, le=10)
    gap_note: str = Field(default="", max_length=200)


class GapDimension(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    # current 由服务端从观己能力快照回填（无数据时为 0），绝不采信模型提供的现值
    current: float = Field(ge=0, le=10)
    target: float = Field(ge=0, le=10)
    gap_note: str = Field(default="", max_length=200)


class GapAnalysisAiPlan(BaseModel):
    """模型输出结构：维度名必须逐字复用输入清单。"""

    overall_note: str = Field(min_length=2, max_length=800)
    dimensions: list[GapDimensionAi] = Field(min_length=3, max_length=8)


class GapAnalysisResponse(BaseModel):
    position: str
    has_data: bool
    completed_interviews: int
    average_score: float | None
    dimensions: list[GapDimension]
    overall_note: str
    model_name: str | None


class WeeklyNoteAi(BaseModel):
    note: str = Field(min_length=2, max_length=300)


class WeeklyReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    week_start: str
    week_end: str
    days: list[dict]
    totals: dict[str, int]
    interviews_completed: int
    average_score: float | None
    active_days: int
    streak_current: int
    ai_note: str | None
