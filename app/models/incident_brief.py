"""
GovFlow AI — Incident brief model.

An incident brief is a human-readable summary generated (by Langflow / LLM)
after routing and severity assessment, ready for the government reviewer.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class IncidentBrief(BaseModel):
    """Structured incident brief for the human reviewer."""

    complaint_id: str
    summary: str = Field(..., description="One-paragraph plain-language summary of the complaint.")
    location_summary: Optional[str] = Field(None, description="Extracted or inferred location.")
    recommended_department: str
    severity: str
    recommended_sla_days: Optional[int] = Field(None, description="Suggested SLA in calendar days.")
    key_facts: list[str] = Field(default_factory=list, description="Bullet-point key facts.")
    evidence_required: bool = Field(False, description="Whether additional evidence should be requested.")
    generated_at: datetime
    generated_by: str = Field("deterministic-stub", description="Model or flow that generated this brief.")
