from __future__ import annotations
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import unescape
import re
from urllib.request import Request, urlopen
from ..models import EventCategory, NormalizedEvent, ResolutionType, Severity
from ..poller import SourceFetchResult

CHANNEL_URL = "https://t.me/s/ivanovoobl"
SOURCE_ID = "ivanovo-operational-telegram"
_BLOCK_RE = re.compile(r'data-post="([^"]+)"[^>]*>.*?<div class="tgme_widget_message_text[^>]*>(.*?)</div>.*?<time datetime="([^"]+)"', re.S)
_TAGS = re.compile(r"<[^>]+>")
_CLEAR = re.compile(r"отбой\s+(?:опасности\s+)?БПЛА", re.I)
_WARNING = re.compile(r"(?:режим\s+)?опасност(?:ь|и)\s+(?:атаки\s+)?БПЛА", re.I)
_MISSILE_CLEAR = re.compile(r"отбой\s+ракетной\s+опасности", re.I)
_MISSILE = re.compile(r"ракетн(?:ая|ой)\s+опасност", re.I)

def parse_telegram_preview(html: str, *, observed_at: datetime, max_age: timedelta = timedelta(hours=6)):
    events = []
    for match in _BLOCK_RE.finditer(html):
        text = " ".join(_TAGS.sub(" ", unescape(match.group(2))).split())
        if "Оперативный штаб" not in text:
            continue
        try:
            occurred_at = datetime.fromisoformat(match.group(3).replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            continue
        if occurred_at < observed_at - max_age:
            continue
        if _CLEAR.search(text):
            subtype, resolved = "drone_warning", True
        elif _WARNING.search(text):
            subtype, resolved = "drone_warning", False
        elif _MISSILE_CLEAR.search(text):
            subtype, resolved = "missile_warning", True
        elif _MISSILE.search(text):
            subtype, resolved = "missile_warning", False
        else:
            continue
        post = match.group(1)
        digest = sha256(f"{SOURCE_ID}|{post}|{text}".encode()).hexdigest()[:24]
        events.append(NormalizedEvent(
            event_id=f"{SOURCE_ID}:{digest}", source_id=SOURCE_ID,
            event_type="public_safety.air_threat", title=text,
            severity=Severity.CRITICAL, confidence=0.995,
            occurred_at=occurred_at, received_at=observed_at,
            correlation_key=f"region:37:air_threat:{subtype}",
            payload={"url": f"https://t.me/{post}", "text": text, "region_code": "37",
                     "scope": "region", "category": "air_threat", "subtype": subtype,
                     "resolved": resolved, "resolution_type": "all_clear" if resolved else "warning",
                     "source_kind": "official_regional_operational_hq", "channel": "ivanovoobl"},
            resolved=resolved, category=EventCategory.AIR_THREAT, subtype=subtype,
            resolution_type=ResolutionType.ALL_CLEAR if resolved else None,
        ))
    return sorted(events, key=lambda e: e.occurred_at)

class IvanovoOperationalTelegramAdapter:
    def __init__(self, channel_url: str = CHANNEL_URL, *, timeout: float = 10.0, max_age: timedelta = timedelta(hours=6)):
        self.channel_url, self.timeout, self.max_age = channel_url, timeout, max_age
        self.source_id = SOURCE_ID
    def fetch(self) -> SourceFetchResult:
        observed_at = datetime.now(timezone.utc)
        try:
            req = Request(self.channel_url, headers={"User-Agent": "AlertSRV/0.1"})
            with urlopen(req, timeout=self.timeout) as response:
                html = response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            return SourceFetchResult(events=(), detail=f"official Telegram channel unavailable: {exc}")
        events = parse_telegram_preview(html, observed_at=observed_at, max_age=self.max_age)
        return SourceFetchResult(events=tuple(events))
