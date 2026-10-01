"""
GovFlow AI — Complaint Parser.

Attempts to call the Langflow Parser flow when LANGFLOW_FLOW_ID_PARSER is
configured.  Falls back to the deterministic keyword stub if:
  - The flow ID is not set (local demo, no Langflow configured).
  - Langflow is unreachable (LangflowUnavailableError).
  - The flow returns invalid JSON (LangflowInvalidResponseError).

The caller (triage endpoint) decides how to handle the fallback status.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from pydantic import BaseModel, ValidationError

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

_VALID_CATEGORIES = {
    "road_infrastructure",
    "traffic_management",
    "waste_management",
    "flood_drainage",
    "water_supply",
    "electricity",
    "unknown",
}


class _ParserResult(BaseModel):
    category: str
    location_hint: str | None = None
    complaint_summary: str | None = None
    key_issues: list[str] = []

    def model_post_init(self, __context: Any) -> None:
        # Normalise and validate the category
        normalised = self.category.lower().strip()
        if normalised not in _VALID_CATEGORIES:
            logger.warning(
                "Parser returned unknown category %r — defaulting to 'unknown'.",
                self.category,
            )
            normalised = "unknown"
        self.category = normalised


# ---------------------------------------------------------------------------
# Keyword-stub fallback
# ---------------------------------------------------------------------------

_KEYWORD_CATEGORY_MAP: dict[str, str] = {
    "jalan|pothole|aspal|lubang|road|trotoar": "road_infrastructure",
    "lampu merah|traffic|kemacetan|parkir|angkot": "traffic_management",
    "sampah|limbah|polusi|waste|bau": "waste_management",
    "banjir|drainase|got|selokan|flood": "flood_drainage",
    "air bersih|pdam|ledeng|water": "water_supply",
    "listrik|pln|lampu mati|power": "electricity",
}


def _keyword_parse(sanitized_text: str) -> dict:
    lower = sanitized_text.lower()
    category = "unknown"
    for pattern, cat in _KEYWORD_CATEGORY_MAP.items():
        if re.search(pattern, lower):
            category = cat
            break
    return {
        "category": category,
        "location_hint": None,
        "complaint_summary": None,
        "key_issues": [],
        "parsed_by": "keyword-stub",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_complaint(sanitized_text: str) -> dict:
    """
    Extract structured fields from sanitized complaint text.

    Returns a dict with keys:
      category, location_hint, complaint_summary, key_issues, parsed_by

    Tries the Langflow Parser flow first; falls back to keyword stub on any
    error.  Sets ``parsed_by`` to indicate which path was taken.
    """
    flow_id = settings.LANGFLOW_FLOW_ID_PARSER
    if not flow_id:
        return _keyword_parse(sanitized_text)

    try:
        raw = call_flow(flow_id, sanitized_text)
        result = _ParserResult(**raw)
        return {
            "category": result.category,
            "location_hint": result.location_hint,
            "complaint_summary": result.complaint_summary,
            "key_issues": result.key_issues,
            "parsed_by": f"langflow:{flow_id}",
        }
    except LangflowUnavailableError as exc:
        logger.warning("Langflow parser unavailable — falling back to keyword stub. %s", exc)
    except (LangflowInvalidResponseError, ValidationError) as exc:
        logger.warning("Langflow parser returned invalid data — falling back to keyword stub. %s", exc)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Unexpected parser error — falling back to keyword stub. %s", exc)

    fallback = _keyword_parse(sanitized_text)
    fallback["parsed_by"] = "keyword-stub-fallback"
    return fallback
