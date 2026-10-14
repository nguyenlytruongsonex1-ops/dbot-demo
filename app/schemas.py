from typing import Any, Literal
from pydantic import BaseModel, Field

ScenarioName = Literal["slow_query", "lock_contention", "workload_contention", "table_bloat", "execution_error"]

class DiagnoseRequest(BaseModel):
    scenario: ScenarioName = "slow_query"
    prepare: bool = True
    user_context: str = ""

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)

class Evidence(BaseModel):
    source: str
    summary: str
    data: Any = None

class RootCause(BaseModel):
    name: str
    confidence: float = Field(ge=0, le=1)
    evidence: list[str] = []

class Recommendation(BaseModel):
    action: str
    rationale: str
    command: str | None = None
    requires_approval: bool = True

class DiagnosisReport(BaseModel):
    incident_id: str
    scenario: str
    status: str
    root_causes: list[RootCause]
    evidence: list[Evidence]
    recommendations: list[Recommendation]
    agent_trace: list[dict[str, Any]] = []
    summary: str
    mode: str
