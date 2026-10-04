from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Iterable
from urllib.request import Request, urlopen
from xml.etree import ElementTree
import re

from ..models import NormalizedEvent, Severity

DEFAULT_IVANOVO_RSS = (
    "https://37.mchs.gov.ru/deyatelnost/press-centr/operativnaya-informaciya/"
    "shtormovye-i-ekstrennye-preduprezhdeniya/rss"
)


class MchsRssAdapter:
    """Adapter for the official regional MChS emergency-warning RSS feed."""

    source_id = "mchs-ivanovo"

    def __init__(self, rss_url: str = DEFAULT_IVANOVO_RSS, timeout: float = 10.0) -> None:
        self.rss_url = rss_url
        self.timeout = timeout

    def fetch(self) -> list[NormalizedEvent]:
        request = Request(self.rss_url, headers={"User-Agent": "AlertSRV/0.1"})
        with urlopen(request, timeout=self.timeout) as response:
            root = ElementTree.fromstring(response.read())
        return list(self._parse(root))

    def _parse(self, root: ElementTree.Element) -> Iterable[NormalizedEvent]:
        channel = root.find("channel")
        if channel is None:
            raise ValueError("RSS channel missing")
        for item in channel.findall("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
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
                correlation_key=f"mchs:ivanovo:{stable_id}",
                payload={"url": link, "text_html": full_text},
            )
