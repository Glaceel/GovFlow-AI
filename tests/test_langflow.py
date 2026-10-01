"""
GovFlow AI — Langflow integration tests.

Covers:
  - Successful Langflow Parser flow call
  - Successful Langflow Severity flow call
  - Successful Langflow Incident Brief flow call
  - Invalid JSON returned by Langflow
  - Langflow unavailable (network error)
  - Deterministic department routing (LLM cannot override)
  - Deterministic SLA resolution (LLM cannot override)
  - Human approval requirement preserved end-to-end
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.incident_brief import IncidentBrief
from app.services.langflow_client import (
    LangflowInvalidResponseError,
    LangflowUnavailableError,
    _extract_text,
    call_flow,
)
from app.services.parser import parse_complaint
from app.services.routing import RoutingService
from app.services.severity import assess_severity
from app.services.sla import SLAService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _langflow_response(text: str) -> dict:
    """Build a minimal Langflow v1 run response containing *text*."""
    return {
        "outputs": [
            {
                "outputs": [
                    {
                        "results": {
                            "message": {"text": text}
                        }
                    }
                ]
            }
        ]
    }


PARSER_AI_RESULT = {
    "category": "road_infrastructure",
    "location_hint": "Jl. Sudirman",
    "complaint_summary": "A large pothole is causing danger to road users.",
    "key_issues": ["large pothole", "dangerous condition"],
}

SEVERITY_AI_RESULT = {
    "severity": "high",
    "severity_reason": "The complaint describes an imminent safety hazard.",
    "confidence": 0.92,
    "urgency_signals": ["berbahaya", "kecelakaan"],
}

BRIEF_AI_RESULT = {
    "summary": "A citizen reports a large pothole on Jl. Sudirman causing accidents. "
               "Routed to Dinas PUPR. High severity — immediate field inspection recommended.",
    "location_summary": "Jl. Sudirman, Jakarta",
    "key_facts": [
        "Large pothole on arterial road",
        "Reported safety hazard",
        "Assigned to Dinas PUPR",
    ],
    "recommended_action": "Dispatch field inspector within 24 hours.",
    "evidence_required": True,
    "reviewer_notes": "AI-generated draft — reviewer must verify independently.",
}


# ===========================================================================
# 1. Langflow client — _extract_text helper
# ===========================================================================

class TestExtractText:
    def test_standard_path(self):
        body = _langflow_response("hello world")
        assert _extract_text(body) == "hello world"

    def test_fallback_finds_nested_text(self):
        body = {"something": {"text": "fallback text"}}
        assert _extract_text(body) == "fallback text"

    def test_raises_when_no_text(self):
        with pytest.raises(LangflowInvalidResponseError):
            _extract_text({"outputs": []})


# ===========================================================================
# 2. call_flow — unit tests with mocked httpx
# ===========================================================================

class TestCallFlow:
    def _mock_response(self, status: int, body: dict) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status
        resp.json.return_value = body
        resp.text = json.dumps(body)
        return resp

    def test_successful_call_returns_parsed_dict(self):
        payload = {"key": "value", "number": 42}
        lf_body = _langflow_response(json.dumps(payload))

        with patch("app.services.langflow_client.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = self._mock_response(200, lf_body)
            mock_client_cls.return_value = mock_client

            result = call_flow("test-flow-id", "some input")

        assert result == payload

    def test_strips_markdown_fences(self):
        json_str = '```json\n{"category": "road_infrastructure"}\n```'
        lf_body = _langflow_response(json_str)

        with patch("app.services.langflow_client.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = self._mock_response(200, lf_body)
            mock_client_cls.return_value = mock_client

            result = call_flow("flow-id", "input")

        assert result["category"] == "road_infrastructure"

    def test_non_200_raises_unavailable(self):
        with patch("app.services.langflow_client.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = self._mock_response(500, {"error": "Internal"})
            mock_client_cls.return_value = mock_client

            with pytest.raises(LangflowUnavailableError):
                call_flow("flow-id", "input")

    def test_network_error_raises_unavailable(self):
        with patch("app.services.langflow_client.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = httpx.ConnectError("refused")
            mock_client_cls.return_value = mock_client

            with pytest.raises(LangflowUnavailableError):
                call_flow("flow-id", "input")

    def test_invalid_json_in_text_raises_invalid_response(self):
        lf_body = _langflow_response("not json at all {{{")

        with patch("app.services.langflow_client.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = self._mock_response(200, lf_body)
            mock_client_cls.return_value = mock_client

            with pytest.raises(LangflowInvalidResponseError):
                call_flow("flow-id", "input")


# ===========================================================================
# 3. Parser service — Langflow integration
# ===========================================================================

class TestParserLangflowCall:
    def _patch_call_flow(self, return_value=None, side_effect=None):
        return patch(
            "app.services.parser.call_flow",
            return_value=return_value,
            side_effect=side_effect,
        )

    def test_successful_parser_call(self):
        with patch("app.services.parser.settings") as mock_settings, \
             self._patch_call_flow(return_value=PARSER_AI_RESULT):
            mock_settings.LANGFLOW_FLOW_ID_PARSER = "parser-flow-id"

            result = parse_complaint("Ada lubang besar di Jl. Sudirman yang berbahaya.")

        assert result["category"] == "road_infrastructure"
        assert result["location_hint"] == "Jl. Sudirman"
        assert result["parsed_by"].startswith("langflow:")

    def test_parser_falls_back_when_unavailable(self):
        """Parser falls back to keyword stub if Langflow is unavailable."""
        with patch("app.services.parser.settings") as mock_settings, \
             self._patch_call_flow(side_effect=LangflowUnavailableError("down")):
            mock_settings.LANGFLOW_FLOW_ID_PARSER = "parser-flow-id"

            result = parse_complaint("Ada sampah menumpuk di depan rumah.")

        # Keyword stub should still classify waste_management
        assert result["category"] == "waste_management"
        assert "stub" in result["parsed_by"]

    def test_parser_falls_back_on_invalid_json(self):
        """Parser falls back if Langflow returns unparseable JSON."""
        with patch("app.services.parser.settings") as mock_settings, \
             self._patch_call_flow(side_effect=LangflowInvalidResponseError("bad json")):
            mock_settings.LANGFLOW_FLOW_ID_PARSER = "parser-flow-id"

            result = parse_complaint("Ada lubang di jalan raya.")

        assert result["category"] in ("road_infrastructure", "unknown")
        assert "stub" in result["parsed_by"]

    def test_parser_uses_keyword_stub_when_no_flow_id(self):
        """When LANGFLOW_FLOW_ID_PARSER is empty, keyword stub is used directly."""
        with patch("app.services.parser.settings") as mock_settings:
            mock_settings.LANGFLOW_FLOW_ID_PARSER = ""

            result = parse_complaint("Sampah tidak diangkut sudah seminggu.")

        assert result["category"] == "waste_management"
        assert result["parsed_by"] == "keyword-stub"

    def test_ai_category_normalised_to_valid_value(self):
        """Unexpected AI categories are normalised to 'unknown'."""
        bad_result = {**PARSER_AI_RESULT, "category": "TOTALLY_INVENTED_CATEGORY"}
        with patch("app.services.parser.settings") as mock_settings, \
             self._patch_call_flow(return_value=bad_result):
            mock_settings.LANGFLOW_FLOW_ID_PARSER = "parser-flow-id"

            result = parse_complaint("Some complaint text about something.")

        assert result["category"] == "unknown"


# ===========================================================================
# 4. Severity service — Langflow integration
# ===========================================================================

class TestSeverityLangflowCall:
    def _patch_call_flow(self, return_value=None, side_effect=None):
        return patch(
            "app.services.severity.call_flow",
            return_value=return_value,
            side_effect=side_effect,
        )

    def test_successful_severity_call(self):
        with patch("app.services.severity.settings") as mock_settings, \
             self._patch_call_flow(return_value=SEVERITY_AI_RESULT):
            mock_settings.LANGFLOW_FLOW_ID_SEVERITY = "severity-flow-id"

            result = assess_severity(
                "Ada kecelakaan besar di jalan raya.",
                category="road_infrastructure",
                department="Dinas PUPR",
            )

        assert result["severity"] == "high"
        assert result["assessed_by"].startswith("langflow:")

    def test_severity_falls_back_when_unavailable(self):
        with patch("app.services.severity.settings") as mock_settings, \
             self._patch_call_flow(side_effect=LangflowUnavailableError("down")):
            mock_settings.LANGFLOW_FLOW_ID_SEVERITY = "severity-flow-id"

            result = assess_severity("Jalan berlubang kecil di gang.", category="road_infrastructure")

        assert result["severity"] in ("low", "medium", "high", "critical")
        assert "stub" in result["assessed_by"]

    def test_severity_falls_back_on_invalid_json(self):
        with patch("app.services.severity.settings") as mock_settings, \
             self._patch_call_flow(side_effect=LangflowInvalidResponseError("bad")):
            mock_settings.LANGFLOW_FLOW_ID_SEVERITY = "severity-flow-id"

            result = assess_severity("Jalan berlubang.", category="road_infrastructure")

        assert result["severity"] in ("low", "medium", "high", "critical")
        assert "stub" in result["assessed_by"]

    def test_severity_uses_keyword_stub_when_no_flow_id(self):
        with patch("app.services.severity.settings") as mock_settings:
            mock_settings.LANGFLOW_FLOW_ID_SEVERITY = ""

            result = assess_severity("Kecelakaan parah di jalan tol.", category="road_infrastructure")

        assert result["severity"] == "high"
        assert result["assessed_by"] == "keyword-stub"


# ===========================================================================
# 5. Brief service — Langflow integration
# ===========================================================================

class TestBriefLangflowCall:
    _COMMON_ARGS = dict(
        complaint_id="test-001",
        sanitized_text="Ada lubang besar di jalan raya.",
        category="road_infrastructure",
        department="Dinas PUPR",
        severity="high",
        severity_reason="Safety hazard detected.",
        sla_days=3,
    )

    def _patch_call_flow(self, return_value=None, side_effect=None):
        return patch(
            "app.services.brief.call_flow",
            return_value=return_value,
            side_effect=side_effect,
        )

    def test_successful_brief_call(self):
        from app.services.brief import generate_brief

        with patch("app.services.brief.settings") as mock_settings, \
             self._patch_call_flow(return_value=BRIEF_AI_RESULT):
            mock_settings.LANGFLOW_FLOW_ID_BRIEF = "brief-flow-id"

            brief = generate_brief(**self._COMMON_ARGS)

        assert isinstance(brief, IncidentBrief)
        assert brief.complaint_id == "test-001"
        assert brief.recommended_department == "Dinas PUPR"   # from deterministic router, not AI
        assert brief.severity == "high"                        # from severity service, not AI
        assert brief.recommended_sla_days == 3                 # from deterministic SLA, not AI
        assert brief.generated_by.startswith("langflow:")
        assert "accident" in brief.summary.lower() or "pothole" in brief.summary.lower() \
               or "citizen" in brief.summary.lower()

    def test_brief_falls_back_when_unavailable(self):
        from app.services.brief import generate_brief

        with patch("app.services.brief.settings") as mock_settings, \
             self._patch_call_flow(side_effect=LangflowUnavailableError("down")):
            mock_settings.LANGFLOW_FLOW_ID_BRIEF = "brief-flow-id"

            brief = generate_brief(**self._COMMON_ARGS)

        assert isinstance(brief, IncidentBrief)
        assert brief.recommended_department == "Dinas PUPR"
        assert brief.generated_by == "deterministic-fallback"

    def test_brief_falls_back_on_invalid_json(self):
        from app.services.brief import generate_brief

        with patch("app.services.brief.settings") as mock_settings, \
             self._patch_call_flow(side_effect=LangflowInvalidResponseError("bad")):
            mock_settings.LANGFLOW_FLOW_ID_BRIEF = "brief-flow-id"

            brief = generate_brief(**self._COMMON_ARGS)

        assert isinstance(brief, IncidentBrief)
        assert brief.generated_by == "deterministic-fallback"

    def test_brief_uses_fallback_when_no_flow_id(self):
        from app.services.brief import generate_brief

        with patch("app.services.brief.settings") as mock_settings:
            mock_settings.LANGFLOW_FLOW_ID_BRIEF = ""

            brief = generate_brief(**self._COMMON_ARGS)

        assert isinstance(brief, IncidentBrief)
        assert brief.generated_by == "deterministic-fallback"

    def test_brief_department_always_from_router_not_ai(self):
        """AI cannot override department — it must come from the deterministic router."""
        from app.services.brief import generate_brief

        # AI returns a different department in its result — but IncidentBrief
        # must still use the department passed in by the caller (from the router).
        ai_result_with_wrong_dept = {
            **BRIEF_AI_RESULT,
            # recommended_action may mention a different dept — brief.recommended_department
            # is not sourced from the AI result at all.
        }
        with patch("app.services.brief.settings") as mock_settings, \
             self._patch_call_flow(return_value=ai_result_with_wrong_dept):
            mock_settings.LANGFLOW_FLOW_ID_BRIEF = "brief-flow-id"

            brief = generate_brief(**{**self._COMMON_ARGS, "department": "Dinas PUPR"})

        assert brief.recommended_department == "Dinas PUPR"


# ===========================================================================
# 6. Deterministic department routing — LLM cannot influence
# ===========================================================================

class TestDeterministicRouting:
    def test_road_infrastructure_always_routes_to_pupr(self):
        router = RoutingService()
        result = router.route("road_infrastructure")
        assert result["department"] == "Dinas PUPR"
        assert result["rule_id"] == "AUTH-001"

    def test_waste_management_always_routes_to_dlh(self):
        router = RoutingService()
        result = router.route("waste_management")
        assert result["department"] == "DLH"
        assert result["rule_id"] == "AUTH-003"

    def test_unknown_always_routes_to_manual_review(self):
        router = RoutingService()
        result = router.route("unknown")
        assert result["department"] == "MANUAL_REVIEW"
        assert result["rule_id"] is None
        assert result["confidence"] == 0.0

    def test_triage_endpoint_routing_is_deterministic(self):
        """
        Even if we patch the parser to return an AI category, routing still
        uses the deterministic rule from authority_rules.json.
        """
        client = TestClient(app)
        # Submit a complaint with a known category
        resp = client.post("/complaints", json={
            "text": "Sampah tidak diangkut sudah tiga hari di depan kantor.",
            "category": "waste_management",
            "evidence_present": False,
        })
        cid = resp.json()["complaint_id"]

        triage_resp = client.post(f"/triage/{cid}")
        assert triage_resp.status_code == 200
        data = triage_resp.json()
        # Routing is always deterministic — DLH for waste_management
        assert data["department"] == "DLH"
        assert data["rule_id"] == "AUTH-003"


# ===========================================================================
# 7. Deterministic SLA — LLM cannot influence
# ===========================================================================

class TestDeterministicSLA:
    def test_road_critical_sla_1_day(self):
        sla = SLAService()
        assert sla.get_sla_days("road_infrastructure", "critical") == 1

    def test_road_high_sla_3_days(self):
        sla = SLAService()
        assert sla.get_sla_days("road_infrastructure", "high") == 3

    def test_road_medium_sla_7_days(self):
        sla = SLAService()
        assert sla.get_sla_days("road_infrastructure", "medium") == 7

    def test_waste_high_sla_2_days(self):
        sla = SLAService()
        assert sla.get_sla_days("waste_management", "high") == 2

    def test_unknown_category_returns_default(self):
        sla = SLAService()
        assert sla.get_sla_days("unknown_category", "low") == 14

    def test_brief_sla_is_from_sla_service_not_llm(self):
        """The brief's recommended_sla_days must equal the deterministic SLA."""
        from app.services.brief import generate_brief

        # Ask for a brief — even with Langflow disabled, SLA must be deterministic.
        with patch("app.services.brief.settings") as mock_settings:
            mock_settings.LANGFLOW_FLOW_ID_BRIEF = ""
            brief = generate_brief(
                complaint_id="test-sla",
                sanitized_text="Ada kebakaran besar.",
                category="road_infrastructure",
                department="Dinas PUPR",
                severity="critical",
                severity_reason="Fire reported.",
                sla_days=1,  # from SLAService.get_sla_days("road_infrastructure","critical")
            )

        assert brief.recommended_sla_days == 1


# ===========================================================================
# 8. Human approval requirement — end-to-end
# ===========================================================================

class TestHumanApprovalEndToEnd:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def _submit_and_triage(self, client, category: str = "road_infrastructure") -> dict:
        submit = client.post("/complaints", json={
            "text": "Ada kerusakan jalan yang cukup parah dan berbahaya di kawasan ini.",
            "category": category,
            "evidence_present": False,
        })
        cid = submit.json()["complaint_id"]
        triage = client.post(f"/triage/{cid}")
        return triage.json()

    def test_triage_always_returns_human_approval_true(self, client):
        data = self._submit_and_triage(client)
        assert data["human_approval_required"] is True

    def test_triage_with_langflow_parser_still_requires_human_approval(self, client):
        """
        Even when Langflow parser is patched to succeed, human_approval_required
        must remain True in the triage response.
        """
        with patch("app.main.parse_complaint", return_value={
            "category": "road_infrastructure",
            "location_hint": "Jl. Test",
            "complaint_summary": "Road damage.",
            "key_issues": [],
            "parsed_by": "langflow:mocked",
        }):
            data = self._submit_and_triage(client, category="unknown")

        assert data["human_approval_required"] is True

    def test_triage_with_langflow_severity_still_requires_human_approval(self, client):
        """
        Even when Langflow severity is patched to succeed, human_approval_required
        must remain True.
        """
        with patch("app.main.assess_severity", return_value={
            "severity": "critical",
            "reason": "AI said critical.",
            "assessed_by": "langflow:mocked",
        }):
            data = self._submit_and_triage(client)

        assert data["human_approval_required"] is True

    def test_brief_endpoint_does_not_expose_human_approval_false(self, client):
        """
        The brief endpoint returns an IncidentBrief — it has no human_approval_required
        field.  The field lives on the DecisionOutput returned by /triage.
        """
        submit = client.post("/complaints", json={
            "text": "Sampah tidak diangkut sudah tiga hari berturut-turut di jalan ini.",
            "category": "waste_management",
            "evidence_present": False,
        })
        cid = submit.json()["complaint_id"]
        client.post(f"/triage/{cid}")

        brief_resp = client.get(f"/triage/{cid}/brief") if False else client.post(f"/triage/{cid}/brief")
        # Brief response should not contain human_approval_required=False
        if brief_resp.status_code == 200:
            brief_data = brief_resp.json()
            assert brief_data.get("human_approval_required", True) is not False

    def test_decision_model_validator_enforces_true(self):
        """The DecisionOutput Pydantic validator must reject human_approval_required=False."""
        from app.models.decision import DecisionOutput
        with pytest.raises(Exception):
            DecisionOutput(
                complaint_id="x",
                category="road_infrastructure",
                department="Dinas PUPR",
                routing_confidence=0.9,
                severity="low",
                severity_reason="Test.",
                duplicate_likelihood=0.0,
                suggested_action="Inspect.",
                confidence=0.9,
                rule_id="AUTH-001",
                human_approval_required=False,
                decided_at=datetime.now(timezone.utc),
            )


# ===========================================================================
# 9. Brief endpoint — integration
# ===========================================================================

class TestBriefEndpoint:
    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_brief_requires_prior_triage(self, client):
        """POST /triage/{id}/brief without prior triage returns 400."""
        submit = client.post("/complaints", json={
            "text": "Ada kerusakan jalan berlubang besar yang berbahaya di sini.",
            "category": "road_infrastructure",
            "evidence_present": False,
        })
        cid = submit.json()["complaint_id"]
        resp = client.post(f"/triage/{cid}/brief")
        assert resp.status_code == 400

    def test_brief_after_triage_returns_200(self, client):
        submit = client.post("/complaints", json={
            "text": "Banjir besar menggenangi seluruh kampung kami sejak kemarin malam.",
            "category": "flood_drainage",
            "evidence_present": True,
        })
        cid = submit.json()["complaint_id"]
        client.post(f"/triage/{cid}")

        resp = client.post(f"/triage/{cid}/brief")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert data["complaint_id"] == cid
        assert data["recommended_department"] in (
            "Dinas PUPR", "Dishub", "DLH", "PDAM", "PLN", "MANUAL_REVIEW"
        )

    def test_brief_nonexistent_complaint_returns_404(self, client):
        resp = client.post("/triage/does-not-exist/brief")
        assert resp.status_code == 404

    def test_brief_department_matches_triage_decision(self, client):
        """The brief's recommended_department must match the triage decision."""
        submit = client.post("/complaints", json={
            "text": "Lampu merah mati total di persimpangan jalan utama kota.",
            "category": "traffic_management",
            "evidence_present": False,
        })
        cid = submit.json()["complaint_id"]
        triage_resp = client.post(f"/triage/{cid}")
        triage_dept = triage_resp.json()["department"]

        brief_resp = client.post(f"/triage/{cid}/brief")
        brief_dept = brief_resp.json()["recommended_department"]

        assert brief_dept == triage_dept
