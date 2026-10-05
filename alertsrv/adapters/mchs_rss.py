from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Iterable
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from xml.etree import ElementTree
import re

from ..classification import classify_event
from ..hazards import classify_hazard
from ..models import EventCategory, NormalizedEvent, Severity

GENERAL_RSS_TEMPLATE = (
    "https://{code}.mchs.gov.ru/deyatelnost/press-centr/operativnaya-informaciya/rss"
)

_MONTHS = {
    bytes.fromhex(k).decode(): v
    for k, v in {
        "d18fd0bdd0b2d0b0d180d18f": 1, "d184d0b5d0b2d180d0b0d0bbd18f": 2,
        "d0bcd0b0d180d182d0b0": 3, "d0b0d0bfd180d0b5d0bbd18f": 4, "d0bcd0b0d18f": 5,
        "d0b8d18ed0bdd18f": 6, "d0b8d18ed0bbd18f": 7, "d0b0d0b2d0b3d183d181d182d0b0": 8,
        "d181d0b5d0bdd182d18fd0b1d180d18f": 9, "d0bed0bad182d18fd0b1d180d18f": 10,
        "d0bdd0bed18fd0b1d180d18f": 11, "d0b4d0b5d0bad0b0d0b1d180d18f": 12,
    }.items()
}
_DATE_RANGE_SAME_MONTH = re.compile(r"(\d{1,2})\s*-\s*(\d{1,2})\s+([^\W\d_]+)\s+(\d{4})", re.I)
_DATE_RANGE_DIFFERENT_MONTH = re.compile(r"(\d{1,2})\s+([^\W\d_]+)\s*(?:-|[^\W\d_]{2})\s*(\d{1,2})\s+([^\W\d_]+)\s+(\d{4})", re.I)
_WARNING_WORDS = tuple(bytes.fromhex(x).decode() for x in ("d0bfd180d0b5d0b4d183d0bfd180d0b5d0b6d0b4d0b5d0bd", "d188d182d0bed180d0bc"))
_SINGLE_DATE = re.compile(r"(\d{1,2})\s+([^\W\d_]+)\s+(\d{4})", re.I)

def _title_expiry(title: str, tzinfo) -> datetime | None:
    match = _DATE_RANGE_DIFFERENT_MONTH.search(title)
    if match:
        _, _, day2, month2, year = match.groups()
        month = _MONTHS.get(month2.lower())
        if month:
            return datetime(int(year), month, int(day2), 23, 59, 59, tzinfo=tzinfo)
    match = _DATE_RANGE_SAME_MONTH.search(title)
    if match:
        _, day2, month_name, year = match.groups()
        month = _MONTHS.get(month_name.lower())
        if month:
            return datetime(int(year), month, int(day2), 23, 59, 59, tzinfo=tzinfo)
    match = _SINGLE_DATE.search(title)
    if match:
        day, month_name, year = match.groups()
        month = _MONTHS.get(month_name.lower())
        if month:
            return datetime(int(year), month, int(day), 23, 59, 59, tzinfo=tzinfo)
    return None

DEFAULT_IVANOVO_RSS = (
    "https://37.mchs.gov.ru/deyatelnost/press-centr/operativnaya-informaciya/"
    "shtormovye-i-ekstrennye-preduprezhdeniya/rss"
)


class MchsRssAdapter:
    """Adapter for the official regional MChS emergency-warning RSS feed."""

    def __init__(self, rss_url: str = DEFAULT_IVANOVO_RSS, timeout: float = 10.0, source_id: str = "mchs-ivanovo", general_fallback_url: str | None = None) -> None:
        self.rss_url = rss_url
        self.timeout = timeout
        self.source_id = source_id
        self.general_fallback_url = general_fallback_url

    def fetch(self) -> list[NormalizedEvent]:
        try:
            root = self._fetch_root(self.rss_url)
            return list(self._parse(root))
        except HTTPError as exc:
            if exc.code != 404 or not self.general_fallback_url:
                raise
            root = self._fetch_root(self.general_fallback_url)
            return list(self._parse(root, warnings_only=True))

    def _fetch_root(self, url: str) -> ElementTree.Element:
        request = Request(url, headers={"User-Agent": "AlertSRV/0.1"})
        with urlopen(request, timeout=self.timeout) as response:
            return ElementTree.fromstring(response.read())

    def _parse(self, root: ElementTree.Element, warnings_only: bool = False) -> Iterable[NormalizedEvent]:
        channel = root.find("channel")
        if channel is None:
            raise ValueError("RSS channel missing")
        for item in channel.findall("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            if warnings_only and not any(word in title.lower() for word in (_WARNING_WORDS[0], _WARNING_WORDS[1], "warning", "storm")):
                continue
            published = (item.findtext("pubDate") or "").strip()
            full_text = next((e.text or "" for e in item if e.tag.endswith("full-text")), "")
            if not title or not link or not published:
                continue
            received_at = parsedate_to_datetime(published)
            event_id = re.search(r"/(\d+)$", link)
            stable_id = event_id.group(1) if event_id else link
            yield NormalizedEvent(
                event_id=stable_id,
                source_id=self.source_id,
                event_type="weather.emergency_warning",
                title=title,
                severity=Severity.WARNING,
                confidence=0.95,
                occurred_at=received_at,
                received_at=received_at,
                correlation_key=f"{self.source_id}:{stable_id}",
                payload={
                    "url": link,
                    "text_html": full_text,
                    "region_code": self.source_id.removeprefix("mchs-"),
                    "scope": "region",
                    "hazard_class": classify_hazard(f"{title} {full_text}", event_type="weather.emergency_warning"),
                    "category": classify_event(f"{title} {full_text}", event_type="weather.emergency_warning")[0],
                    "subtype": classify_event(f"{title} {full_text}", event_type="weather.emergency_warning")[1],
                },
                expires_at=_title_expiry(title, received_at.tzinfo),
                category=EventCategory(classify_event(f"{title} {full_text}", event_type="weather.emergency_warning")[0]),
                subtype=classify_event(f"{title} {full_text}", event_type="weather.emergency_warning")[1],
            )
