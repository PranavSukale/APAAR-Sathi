from __future__ import annotations

import re
import unicodedata

# Indian-name-aware normalisation.
# Idempotent: normalise(normalise(x)) == normalise(x).

HONORIFICS = {
    "mr", "mrs", "ms", "miss", "dr", "shri", "smt", "kumari", "km", "sri",
    "md", "mohd",  # treated as honorific-ish prefixes only when standalone handled below
}

# Spelling / transliteration variant classes map to a canonical token.
SPELLING_VARIANTS = {
    "mohammed": "mohammad", "mohammad": "mohammad", "muhammad": "mohammad",
    "muhammed": "mohammad", "mohamad": "mohammad", "mohd": "mohammad",
    "abdul": "abdul", "abdool": "abdul",
    "sanjay": "sanjay", "sanjai": "sanjay",
    "rajeev": "rajiv", "rajiv": "rajiv",
    "sunita": "sunita", "suniti": "sunita",
    "lakshmi": "laxmi", "laxmi": "laxmi",
    "krishnan": "krishna", "krishna": "krishna", "krsna": "krishna",
    "shreya": "shriya", "shriya": "shriya",
    "siddharth": "siddharth", "sidharth": "siddharth", "siddhartha": "siddharth",
    "neha": "neha",
    "aishwarya": "aishwarya", "aiswarya": "aishwarya",
    "prajwal": "prajwal", "prajval": "prajwal",
    "deepak": "dipak", "dipak": "dipak",
    "geeta": "gita", "gita": "gita",
    "meena": "mina", "mina": "mina",
}

_PUNCT = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WS = re.compile(r"\s+")
_REPEAT = re.compile(r"(.)\1+")


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def basic_clean(name: str) -> str:
    if name is None:
        return ""
    s = unicodedata.normalize("NFKC", name)
    s = _strip_accents(s)
    s = s.casefold()
    s = _PUNCT.sub(" ", s)
    s = _WS.sub(" ", s).strip()
    return s


def collapse_repeats(token: str) -> str:
    # "reeta" -> "reta" ; keeps a single char. Conservative, aids variant match.
    return _REPEAT.sub(r"\1", token)


def _canon_token(tok: str) -> str:
    # Try variant map on the raw token first, then on the repeat-collapsed form.
    if tok in SPELLING_VARIANTS:
        return SPELLING_VARIANTS[tok]
    collapsed = collapse_repeats(tok)
    return SPELLING_VARIANTS.get(collapsed, collapsed)


def tokens(name: str) -> list[str]:
    s = basic_clean(name)
    raw = [t for t in s.split(" ") if t]
    # drop honorifics only if there is more than one token
    out = []
    for i, t in enumerate(raw):
        if t in HONORIFICS and len(raw) > 1:
            continue
        out.append(_canon_token(t))
    return out or [_canon_token(x) for x in raw]


def sorted_token_key(name: str) -> str:
    """Order-invariant key (handles surname-first vs surname-last)."""
    return " ".join(sorted(tokens(name)))


def initials(name: str) -> str:
    return "".join(t[0] for t in tokens(name) if t)


def phonetic_key(name: str) -> str:
    """Lightweight Soundex-like phonetic key over the sorted tokens (no external dep)."""
    codes = []
    for t in sorted(tokens(name)):
        codes.append(_soundex(t))
    return "-".join(codes)


_SOUNDEX_MAP = {
    **dict.fromkeys("bfpv", "1"),
    **dict.fromkeys("cgjkqsxz", "2"),
    **dict.fromkeys("dt", "3"),
    **dict.fromkeys("l", "4"),
    **dict.fromkeys("mn", "5"),
    **dict.fromkeys("r", "6"),
}


def _soundex(token: str) -> str:
    token = re.sub(r"[^a-z]", "", token)
    if not token:
        return "0000"
    first = token[0].upper()
    tail = token[1:]
    digits = []
    prev = _SOUNDEX_MAP.get(token[0], "")
    for ch in tail:
        code = _SOUNDEX_MAP.get(ch, "")
        if code and code != prev:
            digits.append(code)
        if ch not in "hw":
            prev = code
    return (first + "".join(digits) + "000")[:4]


def feature_bundle(name: str) -> dict:
    """All derived, non-reversible features used for blocking + comparison."""
    toks = tokens(name)
    return {
        "tokens": toks,
        "sorted_token_key": " ".join(sorted(toks)),
        "phonetic_key": phonetic_key(name),
        "first_token": toks[0] if toks else "",
        "initials": initials(name),
        "token_count": len(toks),
    }
