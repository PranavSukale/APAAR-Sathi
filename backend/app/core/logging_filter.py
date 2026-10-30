from __future__ import annotations

import logging
import re

# Redacts identifier-like and name-like values from log records.
# Student endpoint request/response bodies are never logged (enforced in middleware).

_PATTERNS = [
    (re.compile(r"\b\d{12}\b"), "[REDACTED_ID]"),            # 12-digit identifier
    (re.compile(r"\b\d{6,}\b"), "[REDACTED_NUM]"),           # long numbers
    (re.compile(r"(?i)(name\"?\s*[:=]\s*)\"?[^\",}]+"), r"\1[REDACTED_NAME]"),
    (re.compile(r"(?i)(apaar\"?\s*[:=]\s*)\"?[^\",}]+"), r"\1[REDACTED_ID]"),
]


def redact(message: str) -> str:
    out = message
    for pattern, repl in _PATTERNS:
        out = pattern.sub(repl, out)
    return out


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        record.msg = redact(msg)
        record.args = ()
        return True


def install_redaction() -> None:
    root = logging.getLogger()
    f = RedactionFilter()
    for handler in root.handlers:
        handler.addFilter(f)
    # also ensure any new handler without one still filters via root logger
    root.addFilter(f)
