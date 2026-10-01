"""
GovFlow AI — PII Sanitizer.

Deterministic regex-based masking. Raw PII must NEVER be sent to an LLM.
This service runs before any AI processing step.

Patterns covered (Indonesian context):
  - NIK (Nomor Induk Kependudukan): 16-digit national ID
  - Indonesian phone numbers: +62 / 08xx formats
  - Email addresses

NOTE: This is a prototype implementation. Real deployments should use a
certified PII detection library or service and undergo a privacy review.
"""
import re

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Indonesian NIK: exactly 16 digits, optionally separated by spaces/dashes.
# We require word boundaries to avoid matching partial number strings.
_NIK_PATTERN = re.compile(
    r"\b\d{6}[-\s]?\d{6}[-\s]?\d{4}\b"  # condensed forms: 6-6-4 grouping
    r"|\b\d{16}\b",                        # plain 16-digit run
    re.ASCII,
)

# Indonesian phone numbers:
#   +62-xxx-xxxx-xxxx  |  +62xxxxxxxxxx  |  08xxxxxxxx(xx)
_PHONE_PATTERN = re.compile(
    r"(?:\+62[\s\-]?)"           # country code +62 with optional separator
    r"(?:\d[\s\-]?){8,12}"       # 8-12 digits with optional separators
    r"|\b08\d{8,11}\b",          # local format 08xx...
    re.ASCII,
)

# Standard email addresses.
_EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b",
)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def sanitize(text: str) -> str:
    """
    Return a copy of *text* with all detected PII replaced by placeholders.

    Replacement tokens:
      [NIK_MASKED]    — for NIK numbers
      [PHONE_MASKED]  — for phone numbers
      [EMAIL_MASKED]  — for email addresses

    Order matters: NIK before phone to avoid partial overlaps on digit runs.
    """
    text = _NIK_PATTERN.sub("[NIK_MASKED]", text)
    text = _PHONE_PATTERN.sub("[PHONE_MASKED]", text)
    text = _EMAIL_PATTERN.sub("[EMAIL_MASKED]", text)
    return text
