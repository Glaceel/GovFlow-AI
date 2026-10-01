"""
GovFlow AI — Incident Brief Service.

Calls the Langflow Incident Brief flow to generate a human-readable
summary for the government reviewer.

Falls back to a minimal deterministic brief if:
  - LANGFLOW_FLOW_ID_BRIEF is not set.
  - Langflow is unreachable.
  - The flow returns invalid JSON or fails Pydantic validation.

IMPORTANT: The brief is a reviewer aid only.
  human_approval_required remains True regardless of brief content.
  Department and SLA are never sourced from the brief.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ValidationError

from app.config import settings
from app.models.incident_brief import IncidentBrief
from app.services.langflow_client import (
    LangflowInvalidResponseError,
    LangflowUnavailableError,
    call_flow,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic model — validates the AI result before constructing IncidentBrief
# ---------------------------------------------------------------------------


class _BriefResult(BaseModel):
    summary: str
    location_summary: str | None = None
    key_facts: list[str] = Field(default_factory=list)
    recommended_action: str = ""
    evidence_required: bool = False
    reviewer_notes: str = ""


# ---------------------------------------------------------------------------
# Deterministic fallback
# ---------------------------------------------------------------------------

def _minimal_brief(
    complaint_id: str,
    sanitized_text: str,
    category: str,
    department: str,
    severity: str,
    severity_reason: str,
    sla_days: int,
) -> IncidentBrief:
    """Build a bare-minimum brief without AI when Langflow is unavailable."""
    return IncidentBrief(
        complaint_id=complaint_id,
        summary=(
            f"Complaint categorised as '{category}' and routed to {department}. "
            f"Severity assessed as '{severity}'. "
            "AI brief generation was unavailable — manual review required."
        ),
        location_summary=None,
        recommended_department=department,
        severity=severity,
        recommended_sla_days=sla_days,
        key_facts=[
            f"Category: {category}",
            f"Severity: {severity} — {severity_reason}",
            f"Suggested SLA: {sla_days} days",
        ],
        evidence_required=False,
        generated_at=datetime.now(timezone.utc),
        generated_by="deterministic-fallback",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_brief(
    complaint_id: str,
    sanitized_text: str,
    category: str,
    department: str,
    severity: str,
    severity_reason: str,
    sla_days: int,
) -> IncidentBrief:
    """
    Generate an incident brief for the human reviewer.

    Tries the Langflow Brief flow first; falls back to the deterministic
    minimal brief on any error.

    Parameters
    ----------
    complaint_id:    Complaint UUID.
    sanitized_text:  PII-sanitized complaint text.
    category:        Complaint category (from parser, validated by router).
    department:      Responsible department (from deterministic router).
    severity:        Severity level (from severity service).
    severity_reason: Plain-language severity explanation.
    sla_days:        SLA in calendar days (from deterministic SLA service).
    """
    flow_id = settings.LANGFLOW_FLOW_ID_BRIEF
    if not flow_id:
        return _minimal_brief(
            complaint_id, sanitized_text, category, department,
            severity, severity_reason, sla_days,
        )

    # Build a context string that matches the incident_brief prompt template.
    context_input = (
        f"Complaint ID: {complaint_id}\n"
        f"Sanitized complaint text: {sanitized_text}\n"
        f"Category: {category}\n"
        f"Responsible department: {department}\n"
        f"Severity: {severity}\n"
        f"Severity reason: {severity_reason}\n"
        f"Suggested SLA: {sla_days} days"
    )

    try:
        raw = call_flow(flow_id, context_input)
        result = _BriefResult(**raw)
        return IncidentBrief(
            complaint_id=complaint_id,
            summary=result.summary,
            location_summary=result.location_summary,
            recommended_department=department,   # always from deterministic router
            severity=severity,                   # always from severity service
            recommended_sla_days=sla_days,       # always from deterministic SLA
            key_facts=result.key_facts,
            evidence_required=result.evidence_required,
            generated_at=datetime.now(timezone.utc),
            generated_by=f"langflow:{flow_id}",
        )
    except LangflowUnavailableError as exc:
        logger.warning("Langflow brief unavailable — using deterministic fallback. %s", exc)
    except (LangflowInvalidResponseError, ValidationError) as exc:
        logger.warning("Langflow brief returned invalid data — using deterministic fallback. %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unexpected brief error — using deterministic fallback. %s", exc)

    return _minimal_brief(
        complaint_id, sanitized_text, category, department,
        severity, severity_reason, sla_days,
    )
