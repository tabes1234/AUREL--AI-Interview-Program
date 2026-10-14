from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="服务健康状态", examples=["ok"])
    service: str = Field(description="服务名称", examples=["aurel-api"])
    version: str = Field(description="服务版本号", examples=["0.1.0"])
