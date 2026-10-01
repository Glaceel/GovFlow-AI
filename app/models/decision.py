"""
GovFlow AI — Decision / triage output model.

IMPORTANT: human_approval_required is ALWAYS True.
The system never autonomously submits a government action.
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class DecisionOutput(BaseModel):
    """Structured output of the triage pipeline, ready for human review."""

    complaint_id: str
    category: str = Field(..., description="Complaint category determined by triage.")
    department: str = Field(..., description="Responsible government department.")
    routing_confidence: float = Field(..., ge=0.0, le=1.0)
    severity: Literal["low", "medium", "high", "critical"]
    severity_reason: str = Field(..., description="Plain-language explanation of severity score.")
    duplicate_likelihood: float = Field(0.0, ge=0.0, le=1.0)
    suggested_action: str = Field(..., description="Recommended next step for the human reviewer.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall triage confidence.")
    rule_id: Optional[str] = Field(None, description="Authority rule that matched this routing.")
    human_approval_required: bool = Field(
        True,
        description="Always True — no government action may be taken without human sign-off.",
    )
    decided_at: datetime

    @model_validator(mode="after")
    def enforce_human_approval(self) -> "DecisionOutput":
        """Guarantee that human_approval_required can never be set to False."""
        if not self.human_approval_required:
            raise ValueError("human_approval_required must always be True.")
        return self
