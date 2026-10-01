"""
GovFlow AI — SLA Lookup Service.

Deterministic SLA resolution from sla_rules.json.
The LLM never determines the SLA — only this service does.
"""
from __future__ import annotations

import json
from pathlib import Path

_RULES_PATH = Path(__file__).parent.parent / "knowledge" / "sla_rules.json"


class SLAService:
    def __init__(self, rules_path: Path = _RULES_PATH) -> None:
        with rules_path.open(encoding="utf-8") as f:
            raw = json.load(f)
        self._default: int = raw.get("default_sla_days", 14)
        # Build lookup: (category, severity) → sla_days
        self._lookup: dict[tuple[str, str], int] = {}
        for rule in raw.get("rules", []):
            key = (rule["category"].lower(), rule["severity"].lower())
            self._lookup[key] = rule["sla_days"]

    def get_sla_days(self, category: str, severity: str) -> int:
        """
        Return the SLA in calendar days for a given category and severity.

        Falls back to the default SLA if no specific rule matches.
        The LLM must never call this; it is called deterministically after
        routing and severity assessment.
        """
        key = (category.lower().strip(), severity.lower().strip())
        return self._lookup.get(key, self._default)
