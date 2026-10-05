from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html import unescape
import re
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from ..models import NormalizedEvent, Severity
from ..source_catalog import IVANOVO

DEFAULT_SITEMAP_URL = IVANOVO.operational_sitemap_url
DEFAULT_SOURCE_ID = IVANOVO.source_id

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_DESCRIPTION_RE = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
    re.I | re.S,
)
_DESCRIPTION_RE_REVERSED = re.compile(
    r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']',
    re.I | re.S,
)
_TAG_RE = re.compile(r"<[^>]+>")
_WARNING_PATTERNS = (
    ("drone_warning", re.compile(
        r"(?:режим\s+)?опасност(?:ь|и)\s+(?:атаки\s+)?БПЛА|угроз(?:а|ы)\s+атаки\s+БПЛА",
        re.I,
    )),
    ("missile_warning", re.compile(r"ракетн(?:ая|ой)\s+опасност", re.I)),
)
_CLEAR_PATTERNS = (
    ("drone_warning", re.compile(
        r"отбой\s+(?:опасности\s+)?БПЛА|отбой\s+опасности\s+атаки\s+БПЛА",
        re.I,
    )),
    ("missile_warning", re.compile(r"отбой\s+ракетной\s+опасности", re.I)),
)
_TIME_RE = re.compile(
    r"(?:обновлен(?:ие|о)|по\s+состоянию)\s+(?:на|по состоянию на)?\s*(\d{1,2}:\d{2})",
    re.I,
)


def _clean_html(value: str) -> str:
    value = unescape(value or "")
    value = _TAG_RE.sub(" ", value)
    return " ".join(value.split())


def _parse_time(text: str, fallback: datetime) -> datetime:
    match = _TIME_RE.search(text)
    if not match:
        return fallback
    hour, minute = map(int, match.group(1).split(":"))
    return fallback.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _classification(text: str) -> tuple[str, str, bool] | None:
    for subtype, pattern in _CLEAR_PATTERNS:
        if pattern.search(text):
            return "air_threat", subtype, True
    for subtype, pattern in _WARNING_PATTERNS:
        if pattern.search(text):
            return "air_threat", subtype, False
    return None


def parse_operational_page(
    html: str,
    *,
    url: str,
    observed_at: datetime,
    source_id: str = DEFAULT_SOURCE_ID,
) -> list[NormalizedEvent]:
    title_match = _TITLE_RE.search(html)
    title = _clean_html(title_match.group(1)) if title_match else "Оперативный штаб Ивановской области"

    description_match = _DESCRIPTION_RE.search(html) or _DESCRIPTION_RE_REVERSED.search(html)
    if not description_match:
        return []

    raw_description = unescape(description_match.group(1) or "")
    raw_description = re.sub(r"<br\s*/?>", "\n", raw_description, flags=re.I)
    text = _clean_html(raw_description)
    if not text:
        return []

    # The CMS uses both explicit update markers and plain HTML line breaks.
    chunks = [
        part.strip()
        for part in re.split(
            r"\n+|(?=(?:Обновление|По состоянию|Оперативный штаб)\s+(?:на|по состоянию))",
            raw_description,
            flags=re.I,
        )
        if _clean_html(part).strip()
    ]

    events: list[NormalizedEvent] = []
    for index, raw_chunk in enumerate(chunks):
        chunk = _clean_html(raw_chunk)
        classification = _classification(chunk)
        if classification is None:
            continue
        category, subtype, resolved = classification
        occurred_at = _parse_time(chunk, observed_at)
        digest = sha256(
            f"{source_id}|{url}|{index}|{chunk}".encode("utf-8")
        ).hexdigest()[:24]
        events.append(
            NormalizedEvent(
                event_id=f"{source_id}:{digest}",
                source_id=source_id,
                event_type="public_safety.air_threat",
                title=chunk if chunk else title,
                severity=Severity.CRITICAL,
                confidence=0.99,
                occurred_at=occurred_at,
                received_at=observed_at,
                correlation_key=f"region:37:air_threat:{subtype}",
                payload={
                    "url": url,
                    "text": text,
                    "source_title": title,
                    "region_code": "37",
                    "scope": "region",
                    "category": category,
                    "subtype": subtype,
                    "resolved": resolved,
                    "source_kind": "official_regional_operational_hq",
                },
                resolved=resolved,
            )
        )

    # Official pages commonly place the newest all-clear above the original
    # warning. Normalize historical updates oldest-first for causal lifecycle.
    events.reverse()
    return events


class IvanovoOperationalHQAdapter:
    """Official Ivanovo regional-government operational-headquarters adapter."""

    def __init__(
        self,
        sitemap_url: str = DEFAULT_SITEMAP_URL,
        *,
        timeout: float = 10.0,
        source_id: str = DEFAULT_SOURCE_ID,
        scan_days: int = 3,
        max_candidates: int = 40,
    ) -> None:
        self.sitemap_url = sitemap_url
        self.timeout = timeout
        self.source_id = source_id
        self.scan_days = scan_days
        self.max_candidates = max_candidates

    def _fetch(self, url: str) -> bytes:
        request = Request(url, headers={"User-Agent": "AlertSRV/0.1"})
        with urlopen(request, timeout=self.timeout) as response:
            return response.read()

    def _sitemap_urls(self) -> list[tuple[str, datetime]]:
        root = ElementTree.fromstring(self._fetch(self.sitemap_url))
        namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
        sitemap = root.find(f"{namespace}sitemap")
        if sitemap is not None:
            loc = sitemap.findtext(f"{namespace}loc")
            if loc:
                root = ElementTree.fromstring(self._fetch(loc))

        cutoff = datetime.now(timezone.utc) - timedelta(days=self.scan_days)
        rows: list[tuple[str, datetime]] = []
        for item in root.findall(f"{namespace}url"):
            loc = item.findtext(f"{namespace}loc")
            lastmod = item.findtext(f"{namespace}lastmod")
            if not loc or not lastmod:
                continue
            try:
                timestamp = datetime.fromisoformat(lastmod.replace("Z", "+00:00"))
            except ValueError:
                continue
            if timestamp >= cutoff:
                rows.append((loc, timestamp))

        rows.sort(key=lambda row: row[1], reverse=True)
        return rows[: self.max_candidates]

    def fetch(self) -> list[NormalizedEvent]:
        events: list[NormalizedEvent] = []
        for url, lastmod in self._sitemap_urls():
            html = self._fetch(url).decode("utf-8", errors="replace")
            title_match = _TITLE_RE.search(html)
            title = _clean_html(title_match.group(1)) if title_match else ""
            if not re.search(r"оперативн(?:ый|ого) штаб", title, re.I):
                continue
            events.extend(
                parse_operational_page(
                    html,
                    url=urljoin(self.sitemap_url, url),
                    observed_at=lastmod,
                    source_id=self.source_id,
                )
            )
        return events
