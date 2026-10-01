"""
GovFlow AI — Routing Service.

Deterministic rule-based routing.
Reads authority_rules.json and maps complaint categories to departments.

If no rule matches, returns a MANUAL_REVIEW state.
This service never invents an authority — it only returns what the
knowledge base explicitly contains.
"""
from __future__ import annotations

import json
from pathlib import Path
_RULES_PATH = Path(__file__).parent.parent / "knowledge" / "authority_rules.json"


class RoutingService:
    def __init__(self, rules_path: Path = _RULES_PATH) -> None:
        with rules_path.open(encoding="utf-8") as f:
            raw = json.load(f)
        # Build a lookup dict keyed by category for O(1) access.
        self._rules: dict[str, dict] = {r["category"]: r for r in raw}

    def route(self, category: str) -> dict:
        """
        Return routing information for *category*.

        Returns a dict with keys:
          department, rule_id, confidence, suggested_action

        If no rule is found, returns a manual-review fallback.
        """
        rule = self._rules.get(category.lower().strip())
        if rule:
            return {
                "department": rule["department"],
                "rule_id": rule["rule_id"],
                "confidence": rule.get("confidence", 0.9),
                "suggested_action": rule.get("suggested_action", "Forward to department."),
            }

        # Fallback — unknown category → manual review
        return {
            "department": "MANUAL_REVIEW",
            "rule_id": None,
            "confidence": 0.0,
            "suggested_action": (
                "No matching authority rule found. "
                "A human reviewer must determine the correct department."
            ),
        }
