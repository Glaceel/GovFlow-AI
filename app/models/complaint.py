"""
GovFlow AI — Complaint data models.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ComplaintStatus(str, Enum):
    PENDING = "pending"
    TRIAGED = "triaged"
    APPROVED = "approved"
    REJECTED = "rejected"
    CLOSED = "closed"


class ComplaintInput(BaseModel):
    """Payload accepted from the citizen at submission time."""

    text: str = Field(..., min_length=10, description="Raw complaint text from the citizen.")
    location: Optional[str] = Field(None, description="Location or address mentioned in the complaint.")
    category: Optional[str] = Field(None, description="Optional pre-categorisation hint from the submitter.")
    evidence_present: bool = Field(False, description="True if the citizen has attached photos/documents.")


class ComplaintRecord(BaseModel):
    """Full stored complaint record, including sanitized text and metadata."""

    complaint_id: str
    text: str = Field(..., description="Original raw text — stored but never sent to LLM.")
    sanitized_text: str = Field(..., description="PII-masked text — safe for AI processing.")
    location: Optional[str] = None
    category: Optional[str] = None
    evidence_present: bool = False
    status: ComplaintStatus = ComplaintStatus.PENDING
    submitted_at: datetime
