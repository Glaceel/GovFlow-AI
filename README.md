# GovFlow AI

An AI-powered public grievance triage and routing engine that transforms an unstructured citizen complaint into a validated, prioritized, explainable, human-approved government case.

> **Hackathon MVP** — This is a prototype. All rules, routing tables, and AI recommendations are for demonstration purposes only and do not represent official government policy or regulations.

---

## What is GovFlow AI?

Citizens submit complaints in free-form text (e.g., "The road on Jl. Merdeka has a large pothole that caused an accident"). GovFlow AI:

1. **Sanitizes** the input — strips PII before any AI processing.
2. **Parses** the complaint — extracts category, location, and evidence signals.
3. **Routes** it — matches the category against a knowledge base of authority rules to find the responsible department.
4. **Assesses severity** — produces a severity score with a plain-language reason.
5. **Generates an incident brief** — a structured summary ready for a human reviewer.
6. **Requires human approval** — no ticket is submitted or action taken without explicit human sign-off.

---

## Architecture

```
Citizen Input
     │
     ▼
[PII Sanitizer]  ← deterministic regex (NO raw PII to LLM)
     │
     ▼
[Complaint Parser]  ← Langflow / LLM (operates on sanitized text only)
     │
     ▼
[Routing Service]  ← deterministic rules (authority_rules.json)
     │
     ▼
[Severity Service]  ← Langflow / LLM placeholder (deterministic stub for now)
     │
     ▼
[Incident Brief Generator]  ← Langflow / LLM
     │
     ▼
[Human Review Dashboard]  ← REQUIRED before any action
     │
     ▼
[Audit Log]  ← immutable record of AI recommendation + human decision
```

**Guiding principle: "Deterministic where possible, AI where useful, human where consequential."**

---

## IBM Bob's Role

IBM Bob is the AI coding and orchestration assistant used throughout development:

- Scaffolding and code generation for the backend.
- Writing and running tests.
- Reviewing logic for responsible-AI compliance.
- Iterating on prompts stored in `prompts/`.
- Helping integrate Langflow flows into the FastAPI backend.

---

## Langflow's Role

[Langflow](https://github.com/logspace-ai/langflow) is the visual AI workflow runtime used for:

- Composing the LLM pipeline (parse → severity → brief generation).
- Swapping models without changing backend code.
- Exposing a REST endpoint that `app/services/parser.py` and `app/services/severity.py` will call.
- Keeping prompt logic versioned inside `prompts/`.

See `langflow/README.md` for integration instructions.

---

## Human-in-the-Loop Principle

**The system never autonomously submits a government ticket or takes action.**

Every triage result carries `human_approval_required: true`. The `/triage/{complaint_id}` endpoint returns a recommendation object. A human reviewer must explicitly `POST /complaints/{complaint_id}/approve` (future endpoint) before downstream action occurs. This is enforced at the model level — `DecisionOutput.human_approval_required` is always `True` and cannot be overridden by AI output.

---

## Running Locally

### Prerequisites

- Python 3.10+
- pip

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-org/govflow-ai.git
cd govflow-ai

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy and edit environment variables
cp .env.example .env
# Edit .env — set LANGFLOW_BASE_URL if you have Langflow running

# 5. Run the API
uvicorn app.main:app --reload

# 6. Run tests
pytest tests/ -v
```

The API will be available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

---

## Current Limitations

- **No database** — complaints are stored in-memory and lost on restart.
- **No authentication** — any caller can submit or approve complaints.
- **Severity is a stub** — deterministic placeholder only; real AI severity via Langflow is not yet wired.
- **Parser is a stub** — category/location extraction is keyword-based; real LLM parser via Langflow is not yet wired.
- **No frontend** — API only.
- **Prototype rules only** — `authority_rules.json`, `sla_rules.json`, and `sop_rules.json` contain mock data, not official government regulations.
- **No deduplication** — `duplicate_likelihood` is always `0.0` in this version.

---

## Project Structure

```
govflow-ai/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Settings (env vars)
│   ├── models/              # Pydantic data models
│   ├── services/            # Business logic
│   └── knowledge/           # Mock authority/SLA/SOP rules
├── data/                    # Sample complaints and evaluation cases
├── prompts/                 # LLM prompt templates
├── tests/                   # pytest test suite
├── langflow/                # Langflow integration notes
└── docs/                    # Architecture and responsible AI docs
```
