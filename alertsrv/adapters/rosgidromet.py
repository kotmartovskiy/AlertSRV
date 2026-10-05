from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import hashlib
import re
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from ..classification import classify_event
from ..hazards import classify_hazard
from ..models import EventCategory, NormalizedEvent, Severity
from ..poller import SourceFetchResult

DEFAULT_EMERGENCY_URL = "https://www.meteorf.gov.ru/product/emergency/"
DEFAULT_HYDROLOGY_INDEX_URL = "https://www.meteorf.gov.ru/press/polovod2026/"
HYDROLOGY_TITLE_PREFIX = "Опасные и неблагоприятные явления на реках, озерах и водохранилищах Российской Федерации"
_MOSCOW = ZoneInfo("Europe/Moscow")

_MONTHS = dict(zip(
    "января,февраля,марта,апреля,мая,июня,июля,августа,сентября,октября,ноября,декабря".split(","),
    range(1, 13)
))


class _EmergencyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[tuple[str, str]] = []
        self._item_depth = self._date_depth = self._text_depth = 0
        self._date: list[str] = []
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = {v for k, v in attrs if k == "class" and v}
        if tag == "div" and "item" in classes and self._item_depth == 0:
            self._item_depth = 1
            self._date, self._text = [], []
        elif self._item_depth:
            self._item_depth += 1
            if tag == "div" and "date" in classes:
                self._date_depth = self._item_depth
            if tag == "div" and "text" in classes:
                self._text_depth = self._item_depth

    def handle_endtag(self, tag: str) -> None:
        if not self._item_depth:
            return
        if self._date_depth == self._item_depth:
            self._date_depth = 0
        if self._text_depth == self._item_depth:
            self._text_depth = 0
        self._item_depth -= 1
        if self._item_depth == 0 and self._date and self._text:
            self.items.append((" ".join(self._date).strip(), " ".join(self._text).strip()))

    def handle_data(self, data: str) -> None:
        if self._date_depth:
            self._date.append(data.strip())
        elif self._text_depth:
            self._text.append(data.strip())


class RosgidrometEmergencyAdapter:
    def __init__(self, url: str = DEFAULT_EMERGENCY_URL, timeout: float = 15.0, source_id: str = "rosgidromet-emergency") -> None:
        self.url, self.timeout, self.source_id = url, timeout, source_id

    def fetch(self) -> SourceFetchResult:
        request = Request(self.url, headers={"User-Agent": "AlertSRV/0.1"})
        with urlopen(request, timeout=self.timeout) as response:
            parser = _EmergencyParser()
            parser.feed(response.read().decode("utf-8", "replace"))
        events = []
        skipped_items = 0
        for published, body in parser.items:
            occurred_at = self._parse_date(published)
            if occurred_at is None or not body:
                skipped_items += 1
                continue
            stable = f"{occurred_at.isoformat()}:{body}"
            digest = hashlib.sha256(stable.encode("utf-8")).hexdigest()[:24]
            category, subtype = classify_event(body, event_type="weather.emergency_national")
            events.append(NormalizedEvent(
                event_id=f"{self.source_id}:{digest}",
                source_id=self.source_id,
                event_type="weather.emergency_national",
                title=body.split(".")[0][:240],
                severity=Severity.WARNING,
                confidence=0.90,
                occurred_at=occurred_at,
                received_at=datetime.now(timezone.utc),
                correlation_key=f"{self.source_id}:{stable}",
                payload={"url": self.url, "text": body, "scope": "russia",
                         "hazard_class": classify_hazard(body, event_type="weather.emergency_national"),
                         "source_kind": "official_rosgidromet_emergency",
                         "category": category, "subtype": subtype},
                category=EventCategory(category),
                subtype=subtype,
            ))
        detail = None
        parser_degraded = skipped_items > 0
        if parser_degraded:
            detail = f"skipped {skipped_items} malformed emergency feed item(s)"
        return SourceFetchResult(
            events=tuple(events),
            parser_degraded=parser_degraded,
            detail=detail,
        )

    @staticmethod
    def _parse_date(value: str) -> datetime | None:
        value = " ".join(value.split())
        match = re.fullmatch(r"(\d{1,2})\s+([^\s]+)\s+(\d{4})(?:\s+\[(\d{2}):(\d{2})\])?", value)
        if not match:
            return None
        day, month_name, year, hour, minute = match.groups()
        month = _MONTHS.get(month_name.lower())
        if month is None:
            return None
        return datetime(int(year), month, int(day), int(hour or 0), int(minute or 0), tzinfo=timezone.utc)


@dataclass(frozen=True, slots=True)
class HydrologyBulletin:
    url: str
    published_at: datetime


class _HydrologyIndexParser(HTMLParser):
    """Find official hydrology bulletin links and publication dates on the index."""
    def __init__(self) -> None:
        super().__init__()
        self.items: list[HydrologyBulletin] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attrs_map = dict(attrs)
        href = attrs_map.get("href")
        if href:
            self._href = href
            self._text = []

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._href is None:
            return
        title = " ".join(" ".join(self._text).split())
        match = re.match(
            re.escape(HYDROLOGY_TITLE_PREFIX) +
            r"\s+по состоянию на\s+(\d{1,2})\s+([^\s]+)\s+(\d{4})\s*г?\.?",
            title,
            re.I,
        )
        if match:
            day, month_name, year = match.groups()
            month = _MONTHS.get(month_name.lower())
            if month:
                self.items.append(HydrologyBulletin(
                    url=urljoin(DEFAULT_HYDROLOGY_INDEX_URL, self._href),
                    published_at=datetime(int(year), month, int(day), tzinfo=_MOSCOW),
                ))
        self._href = None
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)


class _HydrologyTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._row is not None and self._cell is not None:
            self._row.append(" ".join(" ".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
            self._cell = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


_HYDROLOGY_LEVELS = (
    ("dangerous", re.compile(r"(?:\bопасн\w*\s+явлен|\bОЯ\b)", re.I), Severity.CRITICAL),
    ("unfavorable", re.compile(r"(?:\bнеблагоприятн\w*\s+явлен|\bНЯ\b)", re.I), Severity.WARNING),
    ("floodplain", re.compile(r"пойм", re.I), Severity.WARNING),
)


def _hydrology_classification(text: str) -> tuple[str, Severity]:
    for subtype, pattern, severity in _HYDROLOGY_LEVELS:
        if pattern.search(text):
            return subtype, severity
    return "hydrology", Severity.WARNING


def _forecast_expiration(forecast: str, published_at: datetime) -> datetime | None:
    """Extract an explicit forecast end date; otherwise leave expiry unset."""
    match = re.search(
        r"(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?\s+"
        r"(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)",
        forecast,
        re.I,
    )
    if not match:
        return None
    start, end, month_name = match.groups()
    month = _MONTHS[month_name.lower()]
    day = int(end or start)
    year = published_at.year
    if month < published_at.month and published_at.month - month > 6:
        year += 1
    return datetime(year, month, day, 23, 59, 59, tzinfo=_MOSCOW)


class RosgidrometHydrologyAdapter:
    """Discover and parse current official Rosgidromet hydrology bulletins."""

    def __init__(
        self,
        url: str = DEFAULT_HYDROLOGY_INDEX_URL,
        *,
        timeout: float = 15.0,
        source_id: str = "rosgidromet-hydrology",
        max_bulletin_age: timedelta = timedelta(days=7),
    ) -> None:
        self.url = url
        self.timeout = timeout
        self.source_id = source_id
        self.max_bulletin_age = max_bulletin_age

    def _fetch(self, url: str) -> bytes:
        request = Request(url, headers={"User-Agent": "AlertSRV/0.1"})
        with urlopen(request, timeout=self.timeout) as response:
            return response.read()

    @staticmethod
    def discover_latest(html: str, *, now: datetime, base_url: str = DEFAULT_HYDROLOGY_INDEX_URL) -> HydrologyBulletin | None:
        parser = _HydrologyIndexParser()
        parser.feed(html)
        if base_url != DEFAULT_HYDROLOGY_INDEX_URL:
            parser.items = [HydrologyBulletin(url=urljoin(base_url, item.url), published_at=item.published_at) for item in parser.items]
        candidates = [item for item in parser.items if item.published_at <= now.astimezone(_MOSCOW)]
        return max(candidates, key=lambda item: item.published_at, default=None)

    def fetch(self) -> SourceFetchResult:
        received_at = datetime.now(timezone.utc)
        index_html = self._fetch(self.url).decode("utf-8", "replace")
        bulletin = self.discover_latest(index_html, now=received_at, base_url=self.url)
        if bulletin is None:
            return SourceFetchResult(events=(), detail="no current hydrology bulletin found")
        if bulletin.published_at < received_at.astimezone(_MOSCOW) - self.max_bulletin_age:
            age = received_at.astimezone(_MOSCOW) - bulletin.published_at
            return SourceFetchResult(
                stale=True,
                detail=f"latest hydrology bulletin is {age.days}d old",
            )
        html = self._fetch(bulletin.url).decode("utf-8", "replace")
        events = self.parse(html, url=bulletin.url, received_at=received_at)
        return SourceFetchResult(events=tuple(events))

    def parse(self, html: str, *, url: str, received_at: datetime) -> list[NormalizedEvent]:
        published = self._parse_published_at(html)
        if published < received_at.astimezone(_MOSCOW) - self.max_bulletin_age:
            return []
        parser = _HydrologyTableParser()
        parser.feed(html)
        events: list[NormalizedEvent] = []

        for row in parser.rows:
            if len(row) < 5 or row[0].lower() in {"субъект рф", "федеральный округ"}:
                continue
            region, water_body, point, fact, forecast = row[:5]
            combined = f"{fact} {forecast}".strip()
            if not re.search(r"(опасн|неблагоприятн|\bОЯ\b|\bНЯ\b|пойм|уровень воды ниже)", combined, re.I):
                continue
            subtype, severity = _hydrology_classification(combined)
            expires_at = _forecast_expiration(forecast, published)
            stable = "|".join((region, water_body, point, fact, forecast, published.isoformat()))
            digest = hashlib.sha256(stable.encode("utf-8")).hexdigest()[:24]
            events.append(NormalizedEvent(
                event_id=f"{self.source_id}:{digest}",
                source_id=self.source_id,
                event_type="hydrology.warning",
                title=f"{water_body} — {point}: {fact}",
                severity=severity,
                confidence=0.95,
                occurred_at=published,
                received_at=received_at,
                correlation_key=f"hydrology:{region}:{water_body}:{point}:{subtype}",
                expires_at=expires_at,
                payload={
                    "url": url,
                    "region_name": region,
                    "water_body": water_body,
                    "observation_point": point,
                    "fact": fact,
                    "forecast": forecast,
                    "scope": "region",
                    "category": "hydrology",
                    "subtype": subtype,
                    "hazard_class": "hydrology",
                    "source_kind": "official_rosgidromet_hydrology",
                    "bulletin_published_at": published.isoformat(),
                },
                category=EventCategory.HYDROLOGY,
                subtype=subtype,
            ))
        return events

    @staticmethod
    def _parse_published_at(html: str) -> datetime:
        text = re.sub(r"<[^>]+>", " ", html)
        text = " ".join(text.split())
        match = re.search(
            r"(\d{1,2})\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+(\d{4})",
            text,
            re.I,
        )
        if not match:
            return datetime.now(timezone.utc)
        day, month_name, year = match.groups()
        month = _MONTHS[month_name.lower()]
        return datetime(int(year), month, int(day), tzinfo=_MOSCOW)
