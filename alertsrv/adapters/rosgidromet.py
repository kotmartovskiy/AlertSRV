from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import hashlib
import re
from urllib.request import Request, urlopen

from ..classification import classify_event
from ..hazards import classify_hazard
from ..models import NormalizedEvent, Severity

DEFAULT_EMERGENCY_URL = "https://www.meteorf.gov.ru/product/emergency/"

_MONTHS = dict(zip(
    "\u044f\u043d\u0432\u0430\u0440\u044f,\u0444\u0435\u0432\u0440\u0430\u043b\u044f,\u043c\u0430\u0440\u0442\u0430,\u0430\u043f\u0440\u0435\u043b\u044f,\u043c\u0430\u044f,\u0438\u044e\u043d\u044f,\u0438\u044e\u043b\u044f,\u0430\u0432\u0433\u0443\u0441\u0442\u0430,\u0441\u0435\u043d\u0442\u044f\u0431\u0440\u044f,\u043e\u043a\u0442\u044f\u0431\u0440\u044f,\u043d\u043e\u044f\u0431\u0440\u044f,\u0434\u0435\u043a\u0430\u0431\u0440\u044f".split(","), range(1, 13)
))

class _EmergencyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.items: list[tuple[str, str]] = []
        self._item_depth = 0
        self._date_depth = 0
        self._text_depth = 0
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

    def fetch(self) -> list[NormalizedEvent]:
        request = Request(self.url, headers={"User-Agent": "AlertSRV/0.1"})
        with urlopen(request, timeout=self.timeout) as response:
            parser = _EmergencyParser()
            parser.feed(response.read().decode("utf-8", "replace"))
        events = []
        for published, body in parser.items:
            occurred_at = self._parse_date(published)
            if occurred_at is None or not body:
                continue
            stable = f"{occurred_at.isoformat()}:{body}"
            digest = hashlib.sha256(stable.encode("utf-8")).hexdigest()[:24]
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
                payload={"url": self.url, "text": body, "scope": "russia", "hazard_class": classify_hazard(body, event_type="weather.emergency_national"), "category": classify_event(body, event_type="weather.emergency_national")[0], "subtype": classify_event(body, event_type="weather.emergency_national")[1]},
            ))
        return events

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


DEFAULT_HYDROLOGY_URL = "https://www.meteorf.gov.ru/press/polovod2026/44449/"

class _HydrologyTableParser(HTMLParser):
    """Extract table rows from Rosgidromet hydrology bulletins.

    The parser deliberately captures table structure rather than trying to
    infer geography from prose. Source wording is retained verbatim.
    """
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
            value = " ".join(" ".join(self._cell).split())
            self._row.append(value)
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


class RosgidrometHydrologyAdapter:
    """Parse official Rosgidromet hydrology bulletins into structured events."""

    def __init__(
        self,
        url: str = DEFAULT_HYDROLOGY_URL,
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

    def fetch(self) -> list[NormalizedEvent]:
        html = self._fetch(self.url).decode("utf-8", "replace")
        return self.parse(html, url=self.url, received_at=datetime.now(timezone.utc))

    def parse(self, html: str, *, url: str, received_at: datetime) -> list[NormalizedEvent]:
        published = self._parse_published_at(html)
        if published < received_at - self.max_bulletin_age:
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
                },
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
        return datetime(int(year), month, int(day), tzinfo=timezone.utc)
