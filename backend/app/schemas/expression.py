"""T5 表达客观指标 / T6 多角色工作流的 Pydantic 模型。"""

from datetime import datetime

from pydantic import BaseModel, Field


# ---------- T5 语音服务状态 ----------

class AsrStatusOut(BaseModel):
    configured: bool
    provider: str | None = None
    provider_label: str | None = None
    missing_env: list[str] = Field(default_factory=list)
    preference: str = "auto"
    providers: dict = Field(default_factory=dict, description="各提供方就绪状态与配置指引")


class ExpressionStatusResponse(BaseModel):
    asr: AsrStatusOut
    ark: dict = Field(default_factory=dict, description="{configured, model}")
    audio_limits: dict = Field(default_factory=dict)


# ---------- T5 转录 + 客观指标 ----------

class PauseProfileOut(BaseModel):
    pause_count: int
    longest_pause_ms: int
    total_pause_ms: int
    silence_ratio: float


class AudioMetricsOut(BaseModel):
    available: bool
    unavailable_reason: str | None = None
    duration_ms: int | None = None
    pause: PauseProfileOut | None = None


class SpeechMetricsOut(BaseModel):
    available: bool
    unavailable_reason: str | None = None
    char_count: int = 0
    speech_rate_cpm: float | None = None
    filler_words: dict[str, int] = Field(default_factory=dict)
    filler_total: int = 0


class ExpressionRecordOut(BaseModel):
    id: int
    source: str
    filename: str | None = None
    asr_status: str
    asr_provider: str | None = None
    asr_error: str | None = None
    has_transcript: bool = False
    has_workflow: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class ExpressionTranscribeResponse(BaseModel):
    id: int
    source: str
    transcript: str | None = None
    asr_status: str
    asr_provider: str | None = None
    asr_error: str | None = None
    audio: AudioMetricsOut
    speech: SpeechMetricsOut


class ExpressionDetail(ExpressionRecordOut):
    transcript: str | None = None
    audio_duration_ms: int | None = None
    metrics: dict = Field(default_factory=dict)
    workflow: dict | None = None
    model_name: str | None = None


# ---------- T6 多角色工作流 ----------

class ExpressionAnalyzeRequest(BaseModel):
    text: str | None = Field(default=None, min_length=30, max_length=20000,
                             description="直接粘贴的回答文本（与 analysis_id 二选一）")
    analysis_id: int | None = Field(default=None, description="引用一次转录记录的文本进行分析")


class ExpressionWorkflowResponse(BaseModel):
    id: int
    asr_status: str
    transcript: str | None
    metrics: dict
    workflow: dict
    model_name: str | None
