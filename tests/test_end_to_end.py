"""
GovFlow AI — End-to-end API tests.

Tests the full request lifecycle through the FastAPI application:
  - submit complaint
  - retrieve complaint
  - run triage
  - verify human approval requirement in triage output
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /complaints
# ---------------------------------------------------------------------------

class TestSubmitComplaint:
    def test_submit_basic_complaint(self, client):
        payload = {
            "text": "Ada lubang besar di Jl. Sudirman yang berbahaya bagi pengendara.",
            "location": "Jl. Sudirman, Jakarta",
            "category": "road_infrastructure",
            "evidence_present": False,
        }
        response = client.post("/complaints", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert "complaint_id" in data
        assert data["status"] == "pending"
        assert data["sanitized_text"] is not None

    def test_pii_is_sanitized_in_stored_record(self, client):
        """Raw PII in the text field must appear sanitized in sanitized_text."""
        payload = {
            "text": "NIK saya 3273012505900003 dan email saya warga@test.com. Sampah tidak diangkut.",
            "location": "Jl. Kebon Jeruk",
            "category": "waste_management",
            "evidence_present": False,
        }
        response = client.post("/complaints", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert "3273012505900003" not in data["sanitized_text"]
        assert "warga@test.com" not in data["sanitized_text"]
        assert "[NIK_MASKED]" in data["sanitized_text"]
        assert "[EMAIL_MASKED]" in data["sanitized_text"]

    def test_complaint_text_too_short_rejected(self, client):
        payload = {"text": "short"}
        response = client.post("/complaints", json=payload)
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /complaints/{complaint_id}
# ---------------------------------------------------------------------------

class TestGetComplaint:
    def test_get_existing_complaint(self, client):
        # Submit first
        payload = {
            "text": "Sampah menumpuk di TPS Antapani sudah 3 hari tidak diangkut.",
            "location": "Jl. Antapani",
            "category": "waste_management",
            "evidence_present": True,
        }
        create_resp = client.post("/complaints", json=payload)
        complaint_id = create_resp.json()["complaint_id"]

        # Retrieve
        get_resp = client.get(f"/complaints/{complaint_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["complaint_id"] == complaint_id

    def test_get_nonexistent_complaint_returns_404(self, client):
        response = client.get("/complaints/does-not-exist-00000")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /triage/{complaint_id}
# ---------------------------------------------------------------------------

class TestTriageComplaint:
    def _submit(self, client, category: str) -> str:
        payload = {
            "text": "Ada kerusakan jalan yang cukup parah dan berbahaya di kawasan ini.",
            "location": "Jl. Test",
            "category": category,
            "evidence_present": False,
        }
        resp = client.post("/complaints", json=payload)
        return resp.json()["complaint_id"]

    def test_triage_returns_decision(self, client):
        complaint_id = self._submit(client, "road_infrastructure")
        resp = client.post(f"/triage/{complaint_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "department" in data
        assert "severity" in data
        assert "human_approval_required" in data

    def test_triage_always_requires_human_approval(self, client):
        """The triage response must ALWAYS have human_approval_required=True."""
        complaint_id = self._submit(client, "road_infrastructure")
        resp = client.post(f"/triage/{complaint_id}")
        data = resp.json()
        assert data["human_approval_required"] is True

    def test_triage_known_category_routes_correctly(self, client):
        complaint_id = self._submit(client, "waste_management")
        resp = client.post(f"/triage/{complaint_id}")
        data = resp.json()
        assert data["department"] == "DLH"
        assert data["rule_id"] == "AUTH-003"

    def test_triage_unknown_category_routes_to_manual_review(self, client):
        complaint_id = self._submit(client, "something_unknown")
        resp = client.post(f"/triage/{complaint_id}")
        data = resp.json()
        assert data["department"] == "MANUAL_REVIEW"
        assert data["rule_id"] is None

    def test_triage_nonexistent_complaint_returns_404(self, client):
        resp = client.post("/triage/does-not-exist-00000")
        assert resp.status_code == 404

    def test_triage_updates_complaint_status(self, client):
        complaint_id = self._submit(client, "traffic_management")
        client.post(f"/triage/{complaint_id}")
        get_resp = client.get(f"/complaints/{complaint_id}")
        assert get_resp.json()["status"] == "triaged"
