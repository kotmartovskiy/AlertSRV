from __future__ import annotations
import hashlib
import re
import unicodedata
_WS = re.compile(r"\s+")
def canonical_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).strip().casefold()
    return _WS.sub(" ", value)
def dedup_key(event_id: str, source_id: str) -> str:
    return f"{source_id}:{event_id}"
def content_fingerprint(*, source_id: str, event_type: str, title: str, occurred_at: str) -> str:
    raw = "|".join([canonical_text(source_id), canonical_text(event_type), canonical_text(title), occurred_at])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
