"""T10 观测输出模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LlmCallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    service: str
    model: str
    prompt_version: str
    status: str
    attempts: int
    latency_ms: int
    experiment: bool
    error_type: str | None = None
    error_message: str | None = None
    usage: dict | None = None
    created_at: datetime


class ServiceStats(BaseModel):
    calls: int
    errors: int
    success_rate: float
    avg_latency_ms: float


class LlmStatsOut(BaseModel):
    total: int
    errors: int
    success_rate: float
    avg_latency_ms: float
    by_service: dict[str, ServiceStats]
    by_model: dict[str, ServiceStats]
    experiment_calls: int
