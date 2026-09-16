"""Versioned contracts for reproducible offline planner evaluation."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

EvaluatorAssertion = Literal[
    "schema_valid",
    "date_consistent",
    "budget_consistent",
    "no_critical_conflicts",
    "no_duplicate_pois",
    "source_coverage",
    "tool_success",
    "retry_recovered",
    "resume_success",
    "replan_scope_precise",
]


class EvaluationCase(BaseModel):
    """One immutable scenario and its expected quality assertions."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(..., pattern=r"^eval_[0-9]{3}$")
    category: str = Field(..., min_length=1, max_length=64)
    description: str = Field(..., min_length=1, max_length=300)
    request: dict[str, Any]
    assertions: list[EvaluatorAssertion] = Field(..., min_length=1)
    expected_detections: list[str] = Field(default_factory=list)
    max_latency_ms: int = Field(default=180000, ge=1)
    max_cost_usd: float = Field(default=1.0, ge=0)


class EvaluationDataset(BaseModel):
    """Pinned dataset metadata and travel cases."""

    model_config = ConfigDict(extra="forbid")

    dataset_version: str
    seed: int
    cases: list[EvaluationCase] = Field(..., min_length=30)


class EvaluationObservation(BaseModel):
    """Sanitized output metrics exported by an engine run."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    engine: Literal["legacy", "journey_graph"]
    schema_valid: bool = True
    date_consistent: bool = True
    budget_consistent: bool = True
    critical_conflicts: int = Field(default=0, ge=0)
    duplicate_pois: int = Field(default=0, ge=0)
    source_coverage: float = Field(default=1.0, ge=0, le=1)
    tool_success_rate: float = Field(default=1.0, ge=0, le=1)
    retry_recovered: bool = True
    resume_success: bool = True
    replan_scope_precision: float = Field(default=1.0, ge=0, le=1)
    latency_ms: int = Field(default=0, ge=0)
    model_cost_usd: float = Field(default=0, ge=0)
    detected_issues: list[str] = Field(default_factory=list)
    failure_node: str | None = None
    failure_tool: str | None = None


class CaseEvaluation(BaseModel):
    """Assertion-level result for one case and engine."""

    case_id: str
    engine: str
    passed: bool
    passed_assertions: int
    total_assertions: int
    failed_assertions: list[str]
    failure_node: str | None = None
    failure_tool: str | None = None


class EngineEvaluation(BaseModel):
    """Aggregate quality and operational metrics for one engine."""

    engine: str
    case_count: int
    passed_cases: int
    pass_rate: float
    average_latency_ms: float
    total_model_cost_usd: float
    cases: list[CaseEvaluation]


class EvaluationReport(BaseModel):
    """Reproducible two-engine comparison report."""

    dataset_version: str
    evaluator_version: str
    seed: int
    engines: list[EngineEvaluation]
    winner: str | None
