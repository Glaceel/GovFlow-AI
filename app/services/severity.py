"""
GovFlow AI — Severity Assessment Service.

Attempts to call the Langflow Severity flow when LANGFLOW_FLOW_ID_SEVERITY is
configured.  Falls back to the deterministic keyword heuristic if:
  - The flow ID is not set.
  - Langflow is unreachable.
  - The flow returns invalid JSON or fails Pydantic validation.

Severity levels: low | medium | high | critical
"""
from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import BaseModel, ValidationError, field_validator

from app.config import settings
from app.services.langflow_client import (
    LangflowInvalidResponseError,
    LangflowUnavailableError,
    call_flow,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic model — validates every AI result before use
# ---------------------------------------------------------------------------

SeverityLevel = Literal["low", "medium", "high", "critical"]


class _SeverityResult(BaseModel):
    severity: SeverityLevel
    severity_reason: str
    confidence: float = 0.8
    urgency_signals: list[str] = []

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


# ---------------------------------------------------------------------------
# Keyword-stub fallback (preserved from original implementation)
# ---------------------------------------------------------------------------

_HIGH_SIGNAL_WORDS = {
    "kecelakaan", "accident", "korban", "meninggal", "luka", "darurat",
    "emergency", "kebakaran", "fire", "banjir besar", "longsor", "critical",
}
_MEDIUM_SIGNAL_WORDS = {
    "bahaya", "danger", "rusak parah", "tidak aman", "unsafe",
    "mengganggu", "hambatan", "obstacle",
}


def _keyword_assess(sanitized_text: str) -> dict:
    lower = sanitized_text.lower()
    if any(word in lower for word in _HIGH_SIGNAL_WORDS):
        return {
            "severity": "high",
            "reason": "Complaint text contains keywords associated with safety incidents or emergencies.",
            "assessed_by": "keyword-stub",
        }
    if any(word in lower for word in _MEDIUM_SIGNAL_WORDS):
        return {
            "severity": "medium",
            "reason": "Complaint text contains keywords suggesting a notable hazard or disruption.",
            "assessed_by": "keyword-stub",
        }
    return {
        "severity": "low",
        "reason": "No high-priority keywords detected in complaint text.",
        "assessed_by": "keyword-stub",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def assess_severity(
    sanitized_text: str,
    category: str = "unknown",
    department: str = "unknown",
) -> dict:
    """
    Return a severity assessment dict.

    Keys: severity (str), reason (str), assessed_by (str)

    Tries the Langflow Severity flow first if configured; falls back to the
    keyword heuristic on any error.

    Parameters
    ----------
    sanitized_text: PII-sanitized complaint text.
    category:       Complaint category (for context prompt).
    department:     Responsible department (for context prompt).
    """
    flow_id = settings.LANGFLOW_FLOW_ID_SEVERITY
    if not flow_id:
        return _keyword_assess(sanitized_text)

    # Build a richer context string matching the severity prompt template.
    context_input = (
        f"{sanitized_text}\n\n"
        f"[Category: {category}]\n"
        f"[Department: {department}]"
    )

    try:
        raw = call_flow(flow_id, context_input)
        result = _SeverityResult(**raw)
        return {
            "severity": result.severity,
            "reason": result.severity_reason,
            "assessed_by": f"langflow:{flow_id}",
        }
    except LangflowUnavailableError as exc:
        logger.warning("Langflow severity unavailable — falling back to keyword stub. %s", exc)
    except (LangflowInvalidResponseError, ValidationError) as exc:
        logger.warning("Langflow severity returned invalid data — falling back to keyword stub. %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unexpected severity error — falling back to keyword stub. %s", exc)

    fallback = _keyword_assess(sanitized_text)
    fallback["assessed_by"] = "keyword-stub-fallback"
    return fallback
