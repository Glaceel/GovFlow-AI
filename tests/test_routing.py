"""
GovFlow AI — Routing service tests.

Tests deterministic routing for known and unknown categories,
and verifies the human-approval requirement on the decision model.
"""
import pytest
from app.services.routing import RoutingService
from app.models.decision import DecisionOutput
from datetime import datetime, timezone


@pytest.fixture
def router():
    return RoutingService()


# ---------------------------------------------------------------------------
# Routing for known categories
# ---------------------------------------------------------------------------

class TestKnownCategoryRouting:
    def test_road_infrastructure_routes_to_pupr(self, router):
        result = router.route("road_infrastructure")
        assert result["department"] == "Dinas PUPR"
        assert result["rule_id"] == "AUTH-001"
        assert result["confidence"] > 0.0

    def test_traffic_management_routes_to_dishub(self, router):
        result = router.route("traffic_management")
        assert result["department"] == "Dishub"
        assert result["rule_id"] == "AUTH-002"
        assert result["confidence"] > 0.0

    def test_waste_management_routes_to_dlh(self, router):
        result = router.route("waste_management")
        assert result["department"] == "DLH"
        assert result["rule_id"] == "AUTH-003"
        assert result["confidence"] > 0.0

    def test_category_is_case_insensitive(self, router):
        result = router.route("ROAD_INFRASTRUCTURE")
        assert result["department"] == "Dinas PUPR"

    def test_category_with_whitespace(self, router):
        result = router.route("  waste_management  ")
        assert result["department"] == "DLH"


# ---------------------------------------------------------------------------
# Routing fallback for unknown category
# ---------------------------------------------------------------------------

class TestUnknownCategoryRouting:
    def test_unknown_category_returns_manual_review(self, router):
        result = router.route("unknown_category_xyz")
        assert result["department"] == "MANUAL_REVIEW"
        assert result["rule_id"] is None
        assert result["confidence"] == 0.0

    def test_empty_category_returns_manual_review(self, router):
        result = router.route("")
        assert result["department"] == "MANUAL_REVIEW"

    def test_unknown_returns_suggested_action_text(self, router):
        result = router.route("something_not_in_rules")
        assert "human reviewer" in result["suggested_action"].lower()

    def test_unknown_never_invents_department(self, router):
        """The router must not return any department name for unknown categories."""
        result = router.route("alien_category")
        assert result["department"] == "MANUAL_REVIEW"
        assert result["rule_id"] is None


# ---------------------------------------------------------------------------
# Human approval requirement
# ---------------------------------------------------------------------------

class TestHumanApprovalRequirement:
    def test_decision_model_requires_human_approval(self):
        """DecisionOutput must always have human_approval_required=True."""
        decision = DecisionOutput(
            complaint_id="test-001",
            category="road_infrastructure",
            department="Dinas PUPR",
            routing_confidence=0.95,
            severity="medium",
            severity_reason="Test reason.",
            duplicate_likelihood=0.0,
            suggested_action="Inspect road.",
            confidence=0.95,
            rule_id="AUTH-001",
            human_approval_required=True,
            decided_at=datetime.now(timezone.utc),
        )
        assert decision.human_approval_required is True

    def test_decision_model_rejects_false_human_approval(self):
        """Setting human_approval_required=False must raise a validation error."""
        with pytest.raises(Exception):
            DecisionOutput(
                complaint_id="test-002",
                category="road_infrastructure",
                department="Dinas PUPR",
                routing_confidence=0.95,
                severity="low",
                severity_reason="Test.",
                duplicate_likelihood=0.0,
                suggested_action="Inspect.",
                confidence=0.95,
                rule_id="AUTH-001",
                human_approval_required=False,  # must raise
                decided_at=datetime.now(timezone.utc),
            )
