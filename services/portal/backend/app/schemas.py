"""Validated message contracts at the Portal's API and Redis boundaries."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class IncidentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    incident_id: str = Field(min_length=1, max_length=100)
    block_id: str = Field(min_length=1, max_length=150)
    prediction: Literal["anomaly"] = "anomaly"
    anomaly_probability: float = Field(ge=0, le=1)
    category: str = Field(min_length=1, max_length=100)
    severity: Literal["critical", "high", "medium", "low"]
    evidence_event_ids: list[str] = Field(default_factory=list, max_length=50)
    evidence_summary: str | None = Field(default=None, max_length=2000)
    total_events_analyzed: int | None = Field(default=None, ge=0)
    recommended_action: str = Field(min_length=1, max_length=150)
    model_version: str = Field(min_length=1, max_length=100)
    created_at: str = Field(default_factory=utc_now)

    @field_validator("evidence_event_ids")
    @classmethod
    def normalise_event_ids(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip().upper() for value in values if value.strip()))


class ActionResultIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    action_result_id: str = Field(min_length=1, max_length=100)
    incident_id: str = Field(min_length=1, max_length=100)
    action: str = Field(min_length=1, max_length=150)
    command: str | None = Field(default=None, max_length=500)
    mode: Literal["dry_run"] = "dry_run"
    status: Literal["completed", "skipped", "failed", "pending"]
    reason: str = Field(min_length=1, max_length=500)
    created_at: str = Field(default_factory=utc_now)


class AcknowledgeIn(BaseModel):
    operator: str = Field(default="Minghao", min_length=1, max_length=80)

