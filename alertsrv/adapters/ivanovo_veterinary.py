from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
from html import unescape
import re
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from ..models import NormalizedEvent, Severity

DEFAULT_REGISTRY_URL = "https://vet.ivanovoobl.ru/pravovye-akty/gosudarstvennyy-reestr-npa-sluzhby-vet/reestr-za-2026-god/"
DEFAULT_SOURCE_ID = "ivanovo-veterinary-registry"
TAG_RE = re.compile(r"<[^>]+>")
HREF_RE = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.I | re.S)
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
    subtype = "animal_quarantine" if ANIMAL_RE.search(text) else ("plant_quarantine" if PLANT_RE.search(text) else "public_health_quarantine")
    return subtype, disease(text), bool(CANCEL_RE.search(text))

def doc_number(text: str):
    m = DOC_RE.search(text)
    return m.group(1) if m else None

def references(text: str):
    return list(dict.fromkeys(re.findall(r"(?:приказ|указ)[^№]{0,220}№\s*([0-9]+(?:-[а-яё]+)?)", text, re.I)))

def parse_registry_html(html: str, *, registry_url: str, observed_at: datetime, source_id: str = DEFAULT_SOURCE_ID):
    events = []
    for m in HREF_RE.finditer(html):
        href, raw_title = m.groups()
        title = clean(raw_title)
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
        url = urljoin(registry_url, unescape(href))
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
                     "document_type": "veterinary_service_npa", "geography_precision": "region",
                     "resolved": cancelled},
            resolved=cancelled and bool(refs),
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
