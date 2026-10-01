"""
GovFlow AI — Audit Service.

Records every AI recommendation and corresponding human decision.
This log is append-only and must be preserved even when a complaint
record is updated or deleted.

Current implementation: in-memory list (prototype).
Replace with a write-once database table in production.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


class AuditEntry:
    """Immutable record of one triage event."""

    __slots__ = ("complaint_id", "sanitized_input", "recommendation", "human_decision", "timestamp")

    def __init__(
        self,
        complaint_id: str,
        sanitized_input: str,
        recommendation: dict[str, Any],
        human_decision: Optional[str],
    ) -> None:
        self.complaint_id = complaint_id
        self.sanitized_input = sanitized_input
        self.recommendation = recommendation
        self.human_decision = human_decision
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "complaint_id": self.complaint_id,
            "sanitized_input": self.sanitized_input,
            "recommendation": self.recommendation,
            "human_decision": self.human_decision,
            "timestamp": self.timestamp,
        }


class AuditService:
    """Append-only audit log for triage events."""

    def __init__(self) -> None:
        self._log: list[AuditEntry] = []

    def record(
        self,
        complaint_id: str,
        sanitized_input: str,
        recommendation: dict[str, Any],
        human_decision: Optional[str] = None,
    ) -> AuditEntry:
        entry = AuditEntry(
            complaint_id=complaint_id,
            sanitized_input=sanitized_input,
            recommendation=recommendation,
            human_decision=human_decision,
        )
        self._log.append(entry)
        return entry

    def get_entries(self, complaint_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Return all entries, optionally filtered by complaint_id."""
        if complaint_id:
            return [e.to_dict() for e in self._log if e.complaint_id == complaint_id]
        return [e.to_dict() for e in self._log]
