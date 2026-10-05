from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import re
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from ..models import EventCategory, NormalizedEvent, ResolutionType, Severity

DEFAULT_REGISTRY_URL = "https://vet.ivanovoobl.ru/pravovye-akty/gosudarstvennyy-reestr-npa-sluzhby-vet/reestr-za-2026-god/"
DEFAULT_SOURCE_ID = "ivanovo-veterinary-registry"
TAG_RE = re.compile(r"<[^>]+>")
DOC_RE = re.compile(r"(?:приказ|указ)[^№]{0,220}№\s*([0-9]+(?:-[а-яё]+)?)", re.I)
DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
QUAR_RE = re.compile(r"карантин|ограничительн.*?мероприяти", re.I)
ANIMAL_RE = re.compile(r"животн|крупного\s+рогатого\s+скота|лошад|свин|овец|птиц|рыб|ветерин", re.I)
PLANT_RE = re.compile(r"растен|фитосанитар", re.I)
CANCEL_RE = re.compile(r"отмен(?:а|е|ить).*?карантин", re.I)
DISEASES = (
    ("rabies", r"бешенств"), ("african_swine_fever", r"африканск.*чум.*свин"),
    ("leukosis", r"лейкоз"), ("leptospirosis", r"лептоспироз"),
    ("brucellosis", r"бруцелл"), ("salmonellosis", r"сальмонелл"),
    ("aeromonosis", r"аэромоноз"), ("lumpy_skin_disease", r"узелков.*дерматит"),
)

class _AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self._row_parts = None
        self._row_links = []
        self._link_href = None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs = dict(attrs)
        if tag == "tr":
            self._row_parts = []
            self._row_links = []
        elif tag == "a" and self._row_parts is not None:
            self._link_href = attrs.get("href")
            if self._link_href:
                self._row_links.append(self._link_href)

    def handle_data(self, data):
        if self._row_parts is not None:
            self._row_parts.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "tr" and self._row_parts is not None:
            self.rows.append((self._row_links[:], " ".join(self._row_parts)))
            self._row_parts = None
            self._row_links = []
            self._link_href = None
def clean(value: str) -> str:
    return " ".join(TAG_RE.sub(" ", unescape(value or "")).split())


def disease(text: str) -> str:
    for name, pattern in DISEASES:
        if re.search(pattern, text, re.I):
            return name
    return "other_animal_disease"


def classify(text: str):
    if not QUAR_RE.search(text):
        return None
    subtype = "animal_quarantine" if ANIMAL_RE.search(text) else (
        "plant_quarantine" if PLANT_RE.search(text) else "public_health_quarantine"
    )
    return subtype, disease(text), bool(CANCEL_RE.search(text))


def doc_number(text: str):
    m = DOC_RE.search(text)
    return m.group(1) if m else None


def references(text: str):
    return list(dict.fromkeys(re.findall(
        r"(?:приказ|указ)[^№]{0,220}№\s*([0-9]+(?:-[а-яё]+)?)", text, re.I
    )))


def _affected_areas(text: str):
    areas = []
    seen = set()

    def add(level, name, **extra):
        name = clean(name).strip(" ,.;:")
        if not name:
            return
        key = (level, name, tuple(sorted(extra.items())))
        if key not in seen:
            seen.add(key)
            item = {"level": level, "name": name}
            item.update(extra)
            areas.append(item)

    m = re.search(
        r"эпизоотичес\w*\s+очаг\w*.*?хозяйств\w*\s+(.+?)\s+с\s+кадастровым\s+номером\s+([0-9:]+)",
        text, re.I | re.S,
    )
    if m:
        district = None
        district_match = re.search(
            r"([А-ЯЁ][А-ЯЁа-яё-]+ского\s+(?:района|муниципального\s+округа))",
            text[m.end():],
            re.I,
        )
        if district_match:
            district = district_match.group(1)
        extra = {"cadastral_number": m.group(2)}
        if district:
            extra["district"] = district
        add("farm", m.group(1), **extra)

    for m in re.finditer(
        r"(?:в\s+пределах\s+административных\s+границ\s+)(д\.\s+[^,.]+?)(?=\s+[^.]{0,40}?района|\s+Ивановской\s+области|[,.;])",
        text, re.I,
    ):
        add("settlement", m.group(1), region_code="37")

    for m in re.finditer(
        r"\b(д\.|с\.|г\.|п\.|ст\.)\s*([А-ЯЁ][А-ЯЁа-яё-]+(?:\s+[А-ЯЁ][А-ЯЁа-яё-]+){0,3})\s+"
        r"([А-ЯЁ][А-ЯЁа-яё-]+ского\s+(?:сельского\s+поселения|муниципального\s+округа|района))",
        text,
    ):
        add("settlement", f"{m.group(1)} {m.group(2)}", municipality=m.group(3), region_code="37")

    for m in re.finditer(
        r"(?:в\s+пределах\s+административных\s+границ\s+)?"
        r"([А-ЯЁ][А-ЯЁа-яё-]+ского\s+(?:муниципального\s+округа|района))\s+Ивановской\s+области",
        text,
    ):
        add("municipality", m.group(1), region_code="37")

    return areas
def parse_registry_html(html: str, *, registry_url: str, observed_at: datetime, source_id: str = DEFAULT_SOURCE_ID):
    parser = _AnchorParser()
    parser.feed(html)
    rows = parser.rows
    if not rows:
        # Unit-test fixtures and minimal upstream pages may contain a bare <a>.
        rows = [
            ([m.group(1)], m.group(2))
            for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.I | re.S)
        ]
    events = []
    for links, raw_row in rows:
        title = clean(raw_row)
        info = classify(title)
        if info is None:
            continue
        subtype, disease_name, cancelled = info
        dm = DATE_RE.search(title)
        occurred = observed_at
        if dm:
            day, month, year = map(int, dm.groups())
            try:
                occurred = observed_at.replace(year=year, month=month, day=day, hour=0, minute=0, second=0, microsecond=0)
            except ValueError:
                pass
        number = doc_number(title)
        refs = [ref for ref in references(title) if ref != number]
        if not cancelled and number:
            key = f"quarantine:37:{disease_name}:order:{number}"
        elif cancelled and refs:
            key = f"quarantine:37:{disease_name}:order:{refs[-1]}"
        else:
            key = "quarantine:37:%s:unresolved:%s" % (disease_name, sha256(title.encode()).hexdigest()[:16])
        url = urljoin(registry_url, unescape(links[0])) if links else registry_url
        digest = sha256(f"{source_id}|{url}|{title}".encode()).hexdigest()[:24]
        events.append(NormalizedEvent(
            event_id=f"{source_id}:{digest}",
            source_id=source_id,
            event_type="quarantine.animal" if subtype == "animal_quarantine" else "quarantine.other",
            title=title, severity=Severity.WARNING, confidence=0.99,
            occurred_at=occurred, received_at=observed_at, correlation_key=key,
            payload={"url": url, "text": title, "region_code": "37", "scope": "region",
                     "category": "quarantine", "subtype": subtype, "disease": disease_name,
                     "document_number": number, "referenced_document_numbers": refs,
                     "document_type": "veterinary_service_npa",
                     "geography_precision": "region", "affected_areas": _affected_areas(title),
                     "resolved": cancelled},
            resolved=cancelled and bool(refs),
            category=EventCategory.QUARANTINE,
            subtype=subtype,
            resolution_type=ResolutionType.CANCEL if cancelled and bool(refs) else None,
        ))
    return events


class IvanovoVeterinaryRegistryAdapter:
    def __init__(self, registry_url: str = DEFAULT_REGISTRY_URL, *, timeout: float = 10.0, source_id: str = DEFAULT_SOURCE_ID):
        self.registry_url, self.timeout, self.source_id = registry_url, timeout, source_id

    def _fetch(self, url: str) -> bytes:
        with urlopen(Request(url, headers={"User-Agent": "AlertSRV/0.1"}), timeout=self.timeout) as response:
            return response.read()

    def fetch(self):
        html = self._fetch(self.registry_url).decode("utf-8", errors="replace")
        return parse_registry_html(html, registry_url=self.registry_url, observed_at=datetime.now(timezone.utc), source_id=self.source_id)
