"""知途高级能力（第十五阶段）的请求/响应模型：图谱、路径比较、检索、记忆、复盘、评测。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

GRAPH_ENTITY_TYPES = {
    "skill", "required_skill", "experience", "direction",
    "target_position", "evidence", "improvement_task",
}
GRAPH_NODE_STATUSES = {"verified", "user_stated", "ai_inferred", "pending"}
GRAPH_EDGE_RELATIONS = {"proves", "requires", "targets", "practice_for", "improves", "related_to"}


class GraphSyncRequest(BaseModel):
    """同步本人真实数据到图谱与检索索引（幂等）。"""

    include_knowledge: bool = True


class GraphNodeStatusUpdate(BaseModel):
    status: str
    note: str | None = Field(default=None, max_length=300)

    @field_validator("status")
    @classmethod
    def _check_status(cls, value: str) -> str:
        if value not in GRAPH_NODE_STATUSES:
            raise ValueError("未知的节点状态")
        return value


class GraphEdgeCreate(BaseModel):
    from_node_id: int
    to_node_id: int
    relation: str

    @field_validator("relation")
    @classmethod
    def _check_relation(cls, value: str) -> str:
        if value not in GRAPH_EDGE_RELATIONS:
            raise ValueError("未知的关系类型")
        return value


class GraphNodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    name: str
    status: str
    confidence: str | None = None
    source_kind: str
    source_ref: dict = {}
    quote: str | None = None
    note: str | None = None
    updated_at: datetime


class GraphEdgeOut(BaseModel):
    id: int
    from_node_id: int
    to_node_id: int
    from_name: str = ""
    to_name: str = ""
    relation: str
    origin: str
    source_kind: str


class GraphOut(BaseModel):
    nodes: list[GraphNodeOut] = []
    edges: list[GraphEdgeOut] = []
    status_counts: dict = {}


class PathCompareRequest(BaseModel):
    directions: list[str] = Field(min_length=2, max_length=4)
    note: str | None = Field(default=None, max_length=300)

    @field_validator("directions")
    @classmethod
    def _clean_directions(cls, value: list[str]) -> list[str]:
        cleaned = []
        for item in value:
            text = str(item or "").strip()[:60]
            if text and text not in cleaned:
                cleaned.append(text)
        if len(cleaned) < 2:
            raise ValueError("至少需要两个有效的职业方向")
        return cleaned


class PathDirectionOut(BaseModel):
    name: str
    relevance: str = ""
    skill_requirements: list[dict] = []
    evidence_gaps: list[str] = []
    interests_constraints: list[str] = []
    learning_cost: str = ""
    verification_actions: list[str] = []
    source: str = "ai_analysis"


class PathComparisonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    note: str
    directions: list[PathDirectionOut] = []
    comparison: dict = {}
    data_basis: dict = {}
    created_at: datetime


class RetrievalSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    top_k: int = Field(default=5, ge=1, le=10)
    industry_id: str | None = Field(default=None, max_length=60)
    occupation_id: str | None = Field(default=None, max_length=80)
    experience_level: str | None = Field(default=None, max_length=30)
    source_kinds: list[str] | None = None

    @field_validator("query")
    @classmethod
    def _strip_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("检索内容不能为空")
        return value


class ReviewApplyRequest(BaseModel):
    adjustments: list[dict] = Field(default_factory=list, max_length=4)


class EvalRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    model: str
    prompt_version: str
    dataset_version: str
    mode: str
    metrics: dict = {}
    created_at: datetime
