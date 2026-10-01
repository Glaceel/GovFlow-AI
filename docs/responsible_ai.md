# GovFlow AI — Responsible AI Principles

## Overview

GovFlow AI is designed around one guiding principle:

> **"Deterministic where possible, AI where useful, human where consequential."**

This document explains how that principle is implemented in the codebase and what responsible-AI boundaries are in place.

---

## 1. Human-in-the-Loop is Non-Negotiable

**The system never autonomously submits a government ticket, takes enforcement action, or contacts a citizen on behalf of government.**

This is enforced at the data model level:

```python
# app/models/decision.py
@model_validator(mode="after")
def enforce_human_approval(self) -> "DecisionOutput":
    if not self.human_approval_required:
        raise ValueError("human_approval_required must always be True.")
    return self
```

`human_approval_required` is a field on every `DecisionOutput`. It cannot be set to `False` — even if an LLM response attempted to do so, the validator would reject it.

---

## 2. PII is Sanitized Before AI Processing

Raw citizen text (which may contain NIK national ID numbers, phone numbers, and email addresses) is **sanitized before any AI call**. The LLM only ever sees `sanitized_text`.

```python
# app/services/sanitizer.py — runs first, before parser/severity
sanitized = sanitize(payload.text)
```

The original `text` is stored for audit purposes but is never transmitted to external services.

---

## 3. AI Recommendations are Clearly Labelled as Drafts

- Severity reasons include the note `[STUB — Langflow AI reasoning not yet connected.]` in the prototype.
- When Langflow is integrated, incident briefs will include `"reviewer_notes"` explicitly stating the output is AI-generated and requires verification.
- The `assessed_by` field in severity output records whether the result came from a keyword stub or an AI model.

---

## 4. Routing is Deterministic

The routing service reads a static `authority_rules.json` and performs exact-match lookups. It does **not** use an LLM for routing decisions.

If no matching rule exists, the system returns `MANUAL_REVIEW` — it never invents a department.

```python
# app/services/routing.py
return {
    "department": "MANUAL_REVIEW",
    "rule_id": None,
    "confidence": 0.0,
    ...
}
```

---

## 5. Knowledge Base is Clearly Marked as Prototype

All JSON files in `app/knowledge/` contain a `"_comment"` field stating:

> `"PROTOTYPE MOCK RULES — not official government regulations."`

These rules are for demonstration purposes only and must be reviewed and replaced with official regulations before any production deployment.

---

## 6. Audit Trail

Every triage event is recorded in the audit log (`app/services/audit.py`) with:
- The sanitized input (not the raw PII text)
- The full AI/deterministic recommendation
- The human decision (when made)
- A timestamp

This log is append-only and must be preserved for accountability.

---

## 7. Current Limitations & Known Risks

| Risk | Current Mitigation | Required Before Production |
|---|---|---|
| PII in raw text | Regex sanitizer before AI | Privacy review + certified PII library |
| AI hallucination in routing | Routing is fully deterministic | N/A |
| AI hallucination in severity/brief | Human must approve | Evaluation framework + accuracy benchmarking |
| No authentication | Not built (prototype) | Auth + RBAC before production |
| In-memory storage | Prototype only | Auditable write-once database |
| Prototype rules | Clearly labelled mock | Official regulatory review |
| No deduplication | `duplicate_likelihood = 0.0` | Similarity search on complaint history |

---

## 8. What This System Will Never Do (by Design)

- Submit a government ticket without human approval.
- Send PII to an LLM.
- Invent a government authority or department name.
- Claim AI recommendations are official government decisions.
- Operate without an audit record.
