from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import hashlib
import re
from urllib.request import Request, urlopen

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
                payload={"url": self.url, "text": body, "scope": "russia"},
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
