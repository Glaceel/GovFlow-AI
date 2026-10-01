# GovFlow AI — Architecture

## Overview

GovFlow AI is a public grievance triage and routing engine. Its purpose is to transform an unstructured citizen complaint into a validated, prioritized, explainable, and human-approved government case.

**Core principle: "Deterministic where possible, AI where useful, human where consequential."**

---

## Component Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                        Citizen                                   │
│              POST /complaints  (raw text + metadata)             │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  PII Sanitizer  (app/services/sanitizer.py)                      │
│  · Deterministic regex — NIK, phone, email                       │
│  · Raw text stored, sanitized_text used for all downstream work  │
└───────────────────────────┬──────────────────────────────────────┘
                            │ sanitized_text only ↓
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  Complaint Parser  (app/services/parser.py)                      │
│  · STUB: keyword-based category extraction                       │
│  · TARGET: Langflow flow → LLM                                   │
│  · Output: category, location_hint                               │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  Routing Service  (app/services/routing.py)                      │
│  · Fully deterministic                                           │
│  · Reads authority_rules.json                                    │
│  · Returns: department, rule_id, confidence                      │
│  · Unknown → MANUAL_REVIEW (never invents a department)          │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  Severity Assessment  (app/services/severity.py)                 │
│  · STUB: keyword heuristic                                       │
│  · TARGET: Langflow flow → LLM                                   │
│  · Output: severity level + plain-language reason                │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  Decision Output  (app/models/decision.py)                       │
│  · Pydantic model                                                │
│  · human_approval_required = True  (enforced, not optional)      │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  Audit Log  (app/services/audit.py)                              │
│  · Records: complaint_id, sanitized_input, recommendation,       │
│    human_decision, timestamp                                     │
│  · Append-only                                                   │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│  Human Reviewer                                                  │
│  · Receives DecisionOutput with human_approval_required=True     │
│  · Must explicitly approve before any government action          │
│  · Approval endpoint: future POST /complaints/{id}/approve       │
└──────────────────────────────────────────────────────────────────┘
```

---

## Data Flow & PII Boundary

```
Raw text (with PII)  →  [Sanitizer]  →  sanitized_text (no PII)
                                              │
                                     All AI/LLM calls use only sanitized_text
```

The raw `text` field is stored in the complaint record for audit/legal purposes but is **never passed to any LLM or external service**.

---

## Knowledge Base

| File | Purpose |
|---|---|
| `authority_rules.json` | Maps complaint categories to responsible departments |
| `sla_rules.json` | Maps category + severity to target SLA in days |
| `sop_rules.json` | Mock SOP guidance steps per category |

All files are **prototype mock data** — not official government regulations.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/complaints` | Submit a new complaint |
| GET | `/complaints/{id}` | Retrieve a complaint |
| POST | `/triage/{id}` | Run triage and return recommendation |

---

## Technology Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI + Uvicorn |
| Data models | Pydantic v2 |
| AI workflow runtime | Langflow (not yet integrated) |
| Configuration | pydantic-settings + .env |
| Testing | pytest |
| Development assistant | IBM Bob |
