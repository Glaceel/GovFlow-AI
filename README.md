# GovFlow AI

> **AI-powered public grievance triage and policy impact engine**

GovFlow AI is a prototype AI intelligence layer that transforms unstructured citizen complaints into **validated, prioritized, explainable, and human-reviewable cases** for public-service officers.

The system is designed to work **alongside existing public complaint channels**, rather than replacing them.

> **Core principle: Deterministic where possible, AI where useful, human where consequential.**
>
> **AI recommends. Human decides.**

---

## Why GovFlow AI?

Public complaints often arrive as free-form text and still require several manual steps before an officer can act:

- understanding what the citizen is reporting,
- identifying the service category,
- determining the responsible department,
- assessing urgency,
- checking the expected service timeline,
- and turning the complaint into an operational case.

GovFlow AI focuses on this **triage and decision-support layer**.

Instead of asking an LLM to make the whole decision, the system separates responsibilities:

| Task | Approach |
|---|---|
| PII sanitization | Deterministic |
| Complaint parsing | AI via Langflow |
| Department routing | Deterministic rules |
| Severity assessment | AI via Langflow + validated fallback |
| SLA recommendation | Deterministic rules |
| Incident brief | AI via Langflow + validated fallback |
| Human approval | Enforced by backend |

This makes the prototype easier to inspect, test, and govern.

---

## What the Prototype Does

### End-to-end flow

```text
Citizen Complaint
       │
       ▼
┌─────────────────────┐
│ PII Sanitization    │
│ deterministic       │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ Complaint Parser     │
│ Langflow + Gemini    │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ Deterministic        │
│ Authority Routing    │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ Severity Assessment  │
│ Langflow + Gemini    │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ Deterministic SLA    │
│ Rules                │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ Incident Brief       │
│ Langflow + Gemini    │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ Human Review         │
│ approval required    │
└─────────────────────┘
```

### Example

Input:

> "Ada lubang besar dan berbahaya di Jl. Sudirman dekat pasar. Lubang ini sudah ada sekitar dua minggu dan kemarin menyebabkan seorang pengendara motor jatuh."

GovFlow can produce a structured result such as:

- **Category:** `road_infrastructure`
- **Department:** `Dinas PUPR`
- **Severity:** `high`
- **Confidence:** model/routing confidence shown in the triage result
- **SLA:** determined by the rule base
- **Location:** extracted from the complaint
- **Key facts:** concrete facts from the complaint
- **Recommended action:** operational next step
- **Human approval:** required

---

## Key Features

### 1. PII Sanitization

Personal identifiers are sanitized before AI processing.

The backend sanitizes complaint text before sending it to Langflow, reducing unnecessary exposure of raw personal information to the model layer.

### 2. AI Complaint Parsing

The Langflow parser extracts structured signals from sanitized complaint text:

- complaint category,
- location hint,
- key issues.

Supported prototype categories include:

- `road_infrastructure`
- `traffic_management`
- `waste_management`
- `public_lighting`
- `water_supply`
- `public_facility`
- `other`

### 3. Deterministic Authority Routing

Department routing is rule-based.

The router reads:

```text
app/knowledge/authority_rules.json
```

If a category does not have a matching authority rule, the system returns:

```text
MANUAL_REVIEW
```

rather than inventing an authority.

### 4. AI Severity Assessment

Severity is assessed through the Langflow Severity flow when configured.

Allowed levels:

```text
low
medium
high
critical
```

The AI response is validated with Pydantic before it is used by the backend.

If Langflow is unavailable or returns invalid output, the service falls back to a deterministic keyword-based heuristic.

### 5. Deterministic SLA

SLA is resolved by the backend from:

```text
app/knowledge/sla_rules.json
```

The LLM does **not** control the department or SLA value.

### 6. AI Incident Brief

The Incident Brief flow converts validated triage data into a concise operational brief containing information such as:

- factual summary,
- location,
- key facts,
- recommended action,
- evidence requirement,
- reviewer notes.

The AI-generated brief is a reviewer aid. Critical routing and SLA values remain controlled by deterministic backend logic.

### 7. Human-in-the-Loop

GovFlow AI does not autonomously execute a government action.

Every triage decision contains:

```json
{
  "human_approval_required": true
}
```

The backend model enforces this requirement.

---

## Responsible AI Design

GovFlow AI follows several safeguards appropriate for a public-service decision-support prototype.

### Privacy

- PII sanitization happens before AI processing.
- Raw PII is not intentionally sent to the Langflow reasoning flows.

### Explainability

The system exposes structured reasoning fields such as:

- severity reason,
- routing rule ID,
- confidence,
- key facts,
- recommended action,
- reviewer notes.

### Human Oversight

AI output is a recommendation, not an autonomous government decision.

The system explicitly requires human review before downstream action.

### Deterministic Controls

Where a decision can be represented as an explicit rule, the prototype keeps it outside the LLM:

- authority routing,
- SLA calculation,
- human approval enforcement.

### Fail-Safe Behavior

AI outputs are validated before use. If Langflow is unavailable or produces invalid structured output, deterministic fallback behavior is used where implemented.

For more detail, see:

```text
docs/responsible_ai.md
```

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI |
| Data validation | Pydantic |
| AI orchestration | Langflow |
| LLM | Google Gemini through Langflow |
| HTTP integration | HTTPX |
| Frontend | HTML + CSS + JavaScript |
| Testing | Pytest |
| Development assistant | IBM Bob |
| Configuration | `.env` / Pydantic Settings |

### Roles of IBM Bob and Langflow

**IBM Bob** is used as an AI development/SDLC assistant for scaffolding, implementation, testing, review, and iteration.

**Langflow** is the runtime AI orchestration layer connecting the backend to the configured Gemini flows.

IBM Bob is therefore not the runtime decision engine.

---

## Project Structure

```text
GovFlow-AI/
│
├── app/
│   ├── main.py
│   ├── config.py
│   │
│   ├── models/
│   │   ├── complaint.py
│   │   ├── decision.py
│   │   └── incident_brief.py
│   │
│   ├── services/
│   │   ├── audit.py
│   │   ├── brief.py
│   │   ├── langflow_client.py
│   │   ├── parser.py
│   │   ├── routing.py
│   │   ├── sanitizer.py
│   │   ├── severity.py
│   │   └── sla.py
│   │
│   └── knowledge/
│       ├── authority_rules.json
│       ├── sla_rules.json
│       └── sop_rules.json
│
├── data/
│   ├── complaints.json
│   └── evaluation_cases.json
│
├── docs/
│   ├── architecture.md
│   └── responsible_ai.md
│
├── frontend/
│   └── index.html
│
├── langflow/
│   └── README.md
│
├── prompts/
│   ├── complaint_parser.txt
│   ├── severity.txt
│   └── incident_brief.txt
│
├── tests/
│   ├── test_end_to_end.py
│   ├── test_langflow.py
│   ├── test_routing.py
│   └── test_sanitizer.py
│
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

---

## Running the Prototype Locally

### Prerequisites

- Python 3.10+
- pip
- Langflow
- A configured Gemini model/API connection in Langflow

### 1. Clone the repository

```bash
git clone https://github.com/Glaceel/GovFlow-AI.git
cd GovFlow-AI
```

### 2. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a local `.env` file.

Example:

```env
LANGFLOW_BASE_URL=http://localhost:7860
LANGFLOW_FLOW_ID_PARSER=<parser-flow-id>
LANGFLOW_FLOW_ID_SEVERITY=<severity-flow-id>
LANGFLOW_FLOW_ID_BRIEF=<brief-flow-id>
```

Do not commit `.env` or API keys to GitHub.

---

## Start Langflow

For the current local demo setup, Langflow is started in PowerShell with:

```powershell
$env:LANGFLOW_SKIP_AUTH_AUTO_LOGIN="true"
langflow run
```

Langflow runs on:

```text
http://localhost:7860
```

The prototype uses three flows:

1. Complaint Parser
2. Severity
3. Incident Brief

The actual flow IDs are configured through `.env`.

---

## Start the FastAPI Backend

Open another PowerShell terminal:

```powershell
cd C:\Users\Lenovo\Documents\govflow-ai
python -m uvicorn app.main:app --reload --port 8000
```

Backend:

```text
http://localhost:8000
```

Interactive API documentation:

```text
http://localhost:8000/docs
```

---

## Start the Frontend Demo

Open a third PowerShell terminal:

```powershell
cd C:\Users\Lenovo\Documents\govflow-ai
python -m http.server 5500 --directory frontend
```

Open:

```text
http://127.0.0.1:5500
```

The frontend sends complaints to the local FastAPI backend and displays the resulting triage recommendation.

---

## API Endpoints

### Submit a complaint

```http
POST /complaints
```

Accepts a citizen complaint and sanitizes PII before storing the complaint record.

### Get a complaint

```http
GET /complaints/{complaint_id}
```

Retrieves a stored complaint record.

### Run triage

```http
POST /triage/{complaint_id}
```

Runs the core pipeline:

```text
sanitization
→ parsing
→ deterministic routing
→ severity assessment
→ deterministic SLA
→ decision
→ audit record
```

### Generate incident brief

```http
POST /triage/{complaint_id}/brief
```

Generates an AI-assisted incident brief after triage.

The department and SLA in the final brief are sourced from validated backend decisions rather than being controlled by the LLM.

---

## Testing

Run the complete test suite:

```bash
pytest tests/ -v
```

The current MVP was validated with:

```text
79 passed
0 failed
```

A deprecation warning from the underlying test stack may appear depending on the installed dependency versions.

---

## Demo Scenarios

### Road infrastructure

```text
Ada lubang besar dan berbahaya di Jl. Sudirman dekat pasar. Lubang ini sudah ada sekitar dua minggu dan kemarin menyebabkan seorang pengendara motor jatuh. Kondisi jalan semakin parah dan membahayakan pengguna jalan yang lewat, terutama pada malam hari.
```

Expected behavior:

```text
Category    → road_infrastructure
Department  → Dinas PUPR
Severity    → high
```

### Waste management

```text
Sampah menumpuk selama hampir satu minggu di sekitar Pasar Cibaduyut. Tumpukan semakin banyak, menimbulkan bau tidak sedap, dan mulai mengganggu aktivitas warga serta pedagang di sekitar pasar.
```

### Public lighting

```text
Lampu penerangan jalan di Jalan Asia Afrika mati sejak tiga malam lalu. Jalan menjadi gelap pada malam hari dan warga yang melintas merasa kondisi tersebut mengganggu keamanan dan kenyamanan pengguna jalan.
```

### PII sanitization

```text
Nama saya Budi Santoso, NIK 3273010101010001 dan nomor HP 081234567890. Saya melaporkan lubang besar dan berbahaya di Jl. Sudirman dekat pasar yang sudah menyebabkan kecelakaan.
```

The purpose of this scenario is to demonstrate that personal identifiers are sanitized before the complaint reaches the AI reasoning layer.

---

## Prototype Scope and Limitations

This repository is a **hackathon prototype**, not a production government system.

Current limitations include:

- complaints are stored in memory and are lost when the backend restarts,
- there is no production authentication or authorization layer,
- authority, SLA, and SOP knowledge files are prototype/mock rules and are not official government regulations,
- Langflow availability is required for the configured AI flows,
- AI outputs depend on the configured model and prompt,
- duplicate likelihood is currently represented in the decision model but is not yet backed by a production-grade duplicate detection engine,
- no real government ticket submission or downstream government action is performed.

These limitations are intentional for the MVP scope.

---

## Future Development

Potential next steps include:

- integration with existing complaint platforms,
- persistent database storage,
- production authentication and role-based access,
- stronger duplicate and similarity detection,
- evidence and attachment verification,
- officer dashboard and queue management,
- configurable authority/SLA knowledge bases,
- monitoring and model evaluation,
- human feedback loops,
- audit and governance tooling,
- multilingual complaint handling,
- analytics for recurring public-service issues.

---

## Design Philosophy

GovFlow AI deliberately avoids making the LLM responsible for every decision.

```text
                    ┌──────────────────────┐
                    │      AI is useful    │
                    │ parsing, severity,   │
                    │ incident brief       │
                    └──────────┬───────────┘
                               │
                               ▼
Citizen ──► Sanitization ──► AI ──► Rules ──► Human Review
                              │       │           │
                              │       │           │
                              ▼       ▼           ▼
                           Explain   Route      Decide
```

The central design principle is:

> **Use AI for unstructured reasoning, deterministic rules for controllable policy logic, and human oversight for consequential decisions.**

---

## Hackathon Context

GovFlow AI was developed as a prototype for the **Hacktiv8 × IBM SkillsBuild National Hackathon 2026 — Public Services** theme.

The prototype focuses on demonstrating:

- a relevant public-service problem,
- an AI-assisted but controlled solution,
- responsible AI safeguards,
- technical feasibility,
- a working end-to-end prototype,
- and a clear path toward integration with existing public-service infrastructure.

---

## License

See [`LICENSE`](LICENSE).

---

## Disclaimer

This project is a demonstration prototype.

The routing tables, SLA rules, SOP rules, prompts, and AI recommendations in this repository are **not official government policies, regulations, or service commitments**.

Any real-world deployment would require appropriate government validation, governance, security, privacy controls, integration agreements, and human oversight.
