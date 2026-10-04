from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import urlparse
import re

MCHS_CONTACTS_URL = "https://mchs.gov.ru/contacts/kontakty-territorialnyh-organov-mchs-rossii"
WARNING_PATH = "/deyatelnost/press-centr/operativnaya-informaciya/shtormovye-i-ekstrennye-preduprezhdeniya/rss"


@dataclass(frozen=True, slots=True)
class MchsRegion:
    code: str
    base_url: str

    @property
    def rss_url(self) -> str:
        return self.base_url.rstrip("/") + WARNING_PATH


class _SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        href = href.strip()
        if re.fullmatch(r"https?://(?:\d+|moscow)\.mchs\.gov\.ru/?", href):
            self.urls.add(href.rstrip("/"))


class MchsRegionalCatalog:
    """Discovers official regional MChS sites from the federal MChS directory."""

    def __init__(self, directory_url: str = MCHS_CONTACTS_URL, timeout: float = 10.0) -> None:
        self.directory_url = directory_url
        self.timeout = timeout

    def discover(self) -> list[MchsRegion]:
        request = Request(self.directory_url, headers={"User-Agent": "AlertSRV/0.1"})
        with urlopen(request, timeout=self.timeout) as response:
            html = response.read().decode("utf-8", "ignore")
        parser = _SiteParser()
        parser.feed(html)
        by_code = {}
        for url in sorted(parser.urls):
            host = urlparse(url).hostname.split(".", 1)[0]
            code = "77" if host == "moscow" else host
            current = by_code.get(code)
            if current is None or url.startswith("https://"):
                by_code[code] = MchsRegion(code=code, base_url=url)
        return sorted(by_code.values(), key=lambda r: int(r.code))
