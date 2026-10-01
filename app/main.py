"""
GovFlow AI — FastAPI application entry point.

Endpoints:
  POST /complaints
  GET  /complaints/{id}
  POST /triage/{complaint_id}
  POST /triage/{complaint_id}/brief
"""

import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.models.complaint import ComplaintInput, ComplaintRecord, ComplaintStatus
from app.models.decision import DecisionOutput
from app.models.incident_brief import IncidentBrief
from app.services.audit import AuditService
from app.services.brief import generate_brief
from app.services.parser import parse_complaint
from app.services.routing import RoutingService
from app.services.sanitizer import sanitize
from app.services.severity import assess_severity
from app.services.sla import SLAService


app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
)


# ---------------------------------------------------------------------------
# CORS
# Allow the local frontend to communicate with the FastAPI backend.
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# In-memory store
# Replaced by a real DB in a future iteration.
# ---------------------------------------------------------------------------

_complaints: dict[str, ComplaintRecord] = {}
_decisions: dict[str, DecisionOutput] = {}

_audit = AuditService()
_router = RoutingService()
_sla = SLAService()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/complaints", response_model=ComplaintRecord, status_code=201)
def submit_complaint(payload: ComplaintInput) -> ComplaintRecord:
    """
    Accept a raw citizen complaint, sanitize PII, and store it.
    Returns the stored record including the sanitized text and assigned ID.
    """

    complaint_id = str(uuid.uuid4())
    sanitized = sanitize(payload.text)

    record = ComplaintRecord(
        complaint_id=complaint_id,
        text=payload.text,
        sanitized_text=sanitized,
        location=payload.location,
        category=payload.category,
        evidence_present=payload.evidence_present,
        status=ComplaintStatus.PENDING,
        submitted_at=datetime.now(timezone.utc),
    )

    _complaints[complaint_id] = record

    return record


@app.get("/complaints/{complaint_id}", response_model=ComplaintRecord)
def get_complaint(complaint_id: str) -> ComplaintRecord:
    """Retrieve a complaint record by its ID."""

    record = _complaints.get(complaint_id)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Complaint not found.",
        )

    return record


@app.post("/triage/{complaint_id}", response_model=DecisionOutput)
def triage_complaint(complaint_id: str) -> DecisionOutput:
    """
    Run triage on a complaint and return a recommendation.

    Pipeline:
      1. PII-sanitized text is sent to the Langflow Parser flow
         if configured, otherwise keyword fallback is used.
      2. Category is passed to deterministic RoutingService.
      3. PII-sanitized text + category + department are sent to
         the Langflow Severity flow if configured.
      4. SLA is resolved deterministically.
      5. Decision is built and recorded in the audit log.

    Department and SLA are always determined deterministically.
    The result always requires human approval before action is taken.
    """

    record = _complaints.get(complaint_id)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Complaint not found.",
        )

    # ------------------------------------------------------------------
    # Step 1: Parse
    # AI parser or keyword fallback.
    # ------------------------------------------------------------------

    if record.category and record.category != "unknown":
        category = record.category
        parsed_by = "submitted-by-citizen"

    else:
        parsed = parse_complaint(record.sanitized_text)
        category = parsed["category"]
        parsed_by = parsed.get(
            "parsed_by",
            "keyword-stub",
        )

    # ------------------------------------------------------------------
    # Step 2: Routing
    # Always deterministic.
    # ------------------------------------------------------------------

    routing_result = _router.route(category)

    # ------------------------------------------------------------------
    # Step 3: Severity
    # AI severity or keyword fallback.
    # ------------------------------------------------------------------

    severity_result = assess_severity(
        record.sanitized_text,
        category=category,
        department=routing_result["department"],
    )

    # ------------------------------------------------------------------
    # Step 4: SLA
    # Always deterministic.
    # ------------------------------------------------------------------

    sla_days = _sla.get_sla_days(
        category,
        severity_result["severity"],
    )

    # ------------------------------------------------------------------
    # Step 5: Build decision
    # ------------------------------------------------------------------

    decision = DecisionOutput(
        complaint_id=complaint_id,
        category=category,
        department=routing_result["department"],
        routing_confidence=routing_result["confidence"],
        severity=severity_result["severity"],
        severity_reason=severity_result["reason"],
        duplicate_likelihood=0.0,
        suggested_action=routing_result["suggested_action"],
        confidence=routing_result["confidence"],
        rule_id=routing_result["rule_id"],
        human_approval_required=True,
        decided_at=datetime.now(timezone.utc),
    )

    # ------------------------------------------------------------------
    # Step 6: Audit
    # ------------------------------------------------------------------

    _audit.record(
        complaint_id=complaint_id,
        sanitized_input=record.sanitized_text,
        recommendation={
            **decision.model_dump(),
            "parsed_by": parsed_by,
            "sla_days": sla_days,
        },
        human_decision=None,
    )

    # ------------------------------------------------------------------
    # Update complaint status and cache decision.
    # ------------------------------------------------------------------

    record.status = ComplaintStatus.TRIAGED
    record.category = category

    _complaints[complaint_id] = record
    _decisions[complaint_id] = decision

    return decision


@app.post(
    "/triage/{complaint_id}/brief",
    response_model=IncidentBrief,
)
def generate_complaint_brief(complaint_id: str) -> IncidentBrief:
    """
    Generate an AI incident brief for the human reviewer.

    Requires the complaint to have been triaged first.

    Department, SLA, and human_approval_required are sourced
    from the triage decision and are never controlled by the LLM.
    """

    record = _complaints.get(complaint_id)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Complaint not found.",
        )

    decision = _decisions.get(complaint_id)

    if decision is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Complaint has not been triaged yet. "
                "Call POST /triage/{complaint_id} first."
            ),
        )

    sla_days = _sla.get_sla_days(
        decision.category,
        decision.severity,
    )

    brief = generate_brief(
        complaint_id=complaint_id,
        sanitized_text=record.sanitized_text,
        category=decision.category,
        department=decision.department,
        severity=decision.severity,
        severity_reason=decision.severity_reason,
        sla_days=sla_days,
    )

    return brief