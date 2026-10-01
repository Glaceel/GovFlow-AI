"""
GovFlow AI — Langflow HTTP client.

Provides a single synchronous helper, `call_flow()`, that:
  1. POSTs the input text to a Langflow flow via the standard run endpoint.
  2. Extracts the model's text reply from the response structure.
  3. Parses and returns the reply as a Python dict (flows are expected to
     output a JSON string).

Error strategy — fail safe, never hallucinate:
  - Network error or timeout  → raises LangflowUnavailableError
  - Non-200 response          → raises LangflowUnavailableError
  - Reply is not valid JSON   → raises LangflowInvalidResponseError

Callers must catch these and fall back to manual review rather than
silently continuing with a fabricated result.
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import settings


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class LangflowUnavailableError(RuntimeError):
    """Raised when Langflow cannot be reached or returns a non-200 status."""


class LangflowInvalidResponseError(ValueError):
    """Raised when the Langflow reply cannot be parsed as valid JSON."""


# ---------------------------------------------------------------------------
# Response parsing helpers
# ---------------------------------------------------------------------------

def _extract_text(response_body: dict) -> str:
    """
    Walk the Langflow v1 run response to find the generated text.

    Langflow returns something like:
    {
      "outputs": [
        {
          "outputs": [
            {
              "results": {
                "message": { "text": "<the model reply>" }
              }
            }
          ]
        }
      ]
    }

    We try the documented path first, then fall back to a broader search.
    Raises LangflowInvalidResponseError if no text can be found.
    """
    try:
        outputs = response_body["outputs"]
        text = outputs[0]["outputs"][0]["results"]["message"]["text"]
        if isinstance(text, str):
            return text
    except (KeyError, IndexError, TypeError):
        pass

    # Broader fallback: look for any "text" key in a depth-first traversal.
    def _find_text(obj: Any) -> str | None:
        if isinstance(obj, dict):
            if "text" in obj and isinstance(obj["text"], str):
                return obj["text"]
            for v in obj.values():
                found = _find_text(v)
                if found is not None:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = _find_text(item)
                if found is not None:
                    return found
        return None

    text = _find_text(response_body)
    if text is not None:
        return text

    raise LangflowInvalidResponseError(
        "Could not locate model text in Langflow response. "
        f"Keys present: {list(response_body.keys())}"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def call_flow(flow_id: str, input_text: str, timeout: float = 30.0) -> dict:
    """
    Call a Langflow flow and return the parsed JSON result as a dict.

    Parameters
    ----------
    flow_id:    The Langflow flow UUID to invoke.
    input_text: The text to send as the chat input.
    timeout:    Request timeout in seconds (default 30 s).

    Returns
    -------
    dict — the parsed JSON object returned by the flow.

    Raises
    ------
    LangflowUnavailableError      — network failure, timeout, or non-200.
    LangflowInvalidResponseError  — the flow reply is not valid JSON.
    """
    url = f"{settings.LANGFLOW_BASE_URL}/api/v1/run/{flow_id}"
    payload = {
        "input_value": input_text,
        "output_type": "chat",
        "input_type": "chat",
    }
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if settings.LANGFLOW_API_KEY:
        headers["x-api-key"] = settings.LANGFLOW_API_KEY

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json=payload, headers=headers)
    except httpx.RequestError as exc:
        raise LangflowUnavailableError(
            f"Langflow request failed for flow {flow_id}: {exc}"
        ) from exc

    if response.status_code != 200:
        raise LangflowUnavailableError(
            f"Langflow returned HTTP {response.status_code} for flow {flow_id}. "
            f"Body: {response.text[:200]}"
        )

    try:
        body = response.json()
    except Exception as exc:
        raise LangflowUnavailableError(
            f"Langflow response body is not JSON for flow {flow_id}."
        ) from exc

    text = _extract_text(body)

    # Strip markdown code fences if the model wrapped the JSON
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        # Remove opening fence (```json or ```) and closing fence
        inner_lines = []
        in_fence = False
        for line in lines:
            if line.startswith("```") and not in_fence:
                in_fence = True
                continue
            if line.startswith("```") and in_fence:
                break
            inner_lines.append(line)
        stripped = "\n".join(inner_lines).strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise LangflowInvalidResponseError(
            f"Flow {flow_id} returned text that is not valid JSON: {exc}. "
            f"Text: {stripped[:300]}"
        ) from exc
