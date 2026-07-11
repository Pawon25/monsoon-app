"""
Lightweight sanitization helpers for free-text fields that get interpolated
into Claude prompts (e.g. `situation`, `additional_notes`, `dwelling_type`).

This is defense-in-depth, not a silver bullet:
1. Pydantic already caps field lengths (see models/schemas.py).
2. Here we strip characters commonly used to break out of a prompt's
   intended structure, and flag messages containing classic
   instruction-override phrasing so the caller can log / drop them.
3. In the prompt templates themselves, all user-supplied text is wrapped
   in clearly delimited blocks with an explicit instruction telling Claude
   to treat the content as data, not as instructions (see prompts/templates.py).
"""
import re
from typing import Optional

_INJECTION_PATTERNS = [
    r"ignore (all )?(previous|prior|above) instructions",
    r"disregard (all )?(previous|prior|above)",
    r"you are now",
    r"system prompt",
    r"act as (a|an) (?!individual|family|resident)",
    r"reveal (the |your )?(prompt|instructions|system)",
    r"\bDAN\b",
    r"jailbreak",
]

_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)

# Strip control characters and characters used for markdown/prompt structure
# abuse (backticks, angle brackets that could fake XML-style tags).
_STRIP_CHARS_RE = re.compile(r"[`<>{}]")


def sanitize_free_text(value: Optional[str]) -> Optional[str]:
    """Clean a free-text field before it is interpolated into a prompt."""
    if not value:
        return value
    cleaned = _STRIP_CHARS_RE.sub("", value)
    cleaned = cleaned.strip()
    return cleaned[:500]


def looks_like_injection(value: Optional[str]) -> bool:
    """Heuristic check for prompt-injection attempts. Used for logging/guarding."""
    if not value:
        return False
    return bool(_INJECTION_RE.search(value))
