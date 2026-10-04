from alertsrv.adapters.mchs_rss import MchsRssAdapter


def test_mchs_rss_fixture(tmp_path):
    xml = '''<?xml version="1.0"?><rss version="2.0"><channel><item><title>Экстренное предупреждение на 04 - 05 октября 2026 года</title><pubDate>Sun, 04 Oct 26 12:12:00 +0300</pubDate><link>https://37.mchs.gov.ru/deyatelnost/press-centr/operativnaya-informaciya/shtormovye-i-ekstrennye-preduprezhdeniya/5836623</link><yandex:full-text xmlns:yandex="http://news.yandex.ru">&lt;p&gt;Ожидается сильный ветер.&lt;/p&gt;</yandex:full-text></item></channel></rss>'''
    path = tmp_path / "mchs.xml"
    path.write_text(xml, encoding="utf-8")
    from xml.etree import ElementTree
    events = list(MchsRssAdapter()._parse(ElementTree.fromstring(xml)))
    assert len(events) == 1
    event = events[0]
    assert event.event_id == "5836623"
    assert event.severity.value == "warning"
    assert event.payload["url"].endswith("5836623")


def test_general_feed_fallback_fixture():
    from xml.etree import ElementTree
    root = ElementTree.Element("rss")
    channel = ElementTree.SubElement(root, "channel")
    for title, link in (("Storm warning", "https://10.mchs.gov.ru/x/1"), ("Operational forecast", "https://10.mchs.gov.ru/x/2")):
        item = ElementTree.SubElement(channel, "item")
        ElementTree.SubElement(item, "title").text = title
        ElementTree.SubElement(item, "pubDate").text = "Sun, 04 Oct 26 12:12:00 +0300"
        ElementTree.SubElement(item, "link").text = link
    adapter = MchsRssAdapter(source_id="mchs-10", general_fallback_url="https://10.mchs.gov.ru/general/rss")
    events = list(adapter._parse(root, warnings_only=True))
    assert len(events) == 1
    assert events[0].title == "Storm warning"

def test_mchs_rss_live_smoke():
    # Explicit live smoke test is opt-in so the normal suite remains offline/deterministic.
    import os
    if os.getenv("ALERTSRV_LIVE_MCHS") != "1":
        return
    events = MchsRssAdapter().fetch()
    assert events


def test_title_expiry_parsing():
    from alertsrv.adapters.mchs_rss import _MONTHS, _title_expiry
    from datetime import timezone
    month = lambda number: next(name for name, value in _MONTHS.items() if value == number)
    tz = timezone.utc
    assert _title_expiry(f"Warning 04 - 05 {month(10)} 2026", tz).day == 5
    assert _title_expiry(f"Warning 30 {month(9)} - 01 {month(10)} 2026", tz).month == 10
    assert _title_expiry(f"Warning 17 {month(9)} 2026", tz).day == 17
