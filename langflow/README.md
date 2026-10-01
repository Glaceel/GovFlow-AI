# Langflow Integration

This directory will contain Langflow flow exports and integration documentation.

## Current Status

**Not yet integrated.** The FastAPI backend uses deterministic stubs for parsing and severity assessment. The Langflow flows will replace these stubs in the next development phase.

---

## Planned Flows

### 1. `complaint_parser_flow.json`
- **Purpose:** Parse a sanitized complaint text and extract category, location, and key issues.
- **Prompt:** `prompts/complaint_parser.txt`
- **Replaces:** `app/services/parser.py` stub
- **Input variable:** `sanitized_text`
- **Expected output:** JSON with `category`, `location_hint`, `key_issues`

### 2. `severity_flow.json`
- **Purpose:** Assess complaint severity with plain-language reasoning.
- **Prompt:** `prompts/severity.txt`
- **Replaces:** `app/services/severity.py` stub
- **Input variables:** `sanitized_text`, `category`, `department`
- **Expected output:** JSON with `severity`, `severity_reason`, `confidence`

### 3. `incident_brief_flow.json`
- **Purpose:** Generate a structured incident brief for the human reviewer.
- **Prompt:** `prompts/incident_brief.txt`
- **Input variables:** `complaint_id`, `sanitized_text`, `category`, `department`, `severity`, `severity_reason`, `sla_days`
- **Expected output:** JSON matching `app/models/incident_brief.py`

---

## Integration Steps

### Step 1 — Set up Langflow

```bash
pip install langflow
langflow run
```

Langflow will start on `http://localhost:7860`.

### Step 2 — Build the flows

1. Open Langflow at `http://localhost:7860`.
2. Create a new flow for each of the three planned flows above.
3. Use the prompt templates from `prompts/` as your prompt text.
4. Configure your LLM component (OpenAI, Ollama, IBM watsonx, etc.).
5. Export each flow as JSON and save to this directory.

### Step 3 — Configure environment variables

Edit your `.env` file:

```
LANGFLOW_BASE_URL=http://localhost:7860
LANGFLOW_FLOW_ID_PARSER=<flow-id-from-langflow>
LANGFLOW_FLOW_ID_SEVERITY=<flow-id-from-langflow>
LANGFLOW_FLOW_ID_BRIEF=<flow-id-from-langflow>
```

### Step 4 — Replace stubs in the backend

In `app/services/parser.py`, replace the stub body of `parse_complaint()`:

```python
import httpx
from app.config import settings

def parse_complaint(sanitized_text: str) -> dict:
    url = f"{settings.LANGFLOW_BASE_URL}/api/v1/run/{settings.LANGFLOW_FLOW_ID_PARSER}"
    headers = {"x-api-key": settings.LANGFLOW_API_KEY} if settings.LANGFLOW_API_KEY else {}
    response = httpx.post(url, json={"input_value": sanitized_text}, headers=headers, timeout=30)
    response.raise_for_status()
    # Parse the Langflow response envelope to extract your JSON output
    return response.json()
```

Apply the same pattern to `app/services/severity.py`.

---

## Architecture Principle Reminder

> **AI where useful, human where consequential.**

Langflow orchestrates the AI reasoning. The human approval gate in `app/models/decision.py` is enforced in Python — it is NOT delegated to the LLM.
