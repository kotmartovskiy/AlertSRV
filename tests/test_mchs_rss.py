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


def test_mchs_rss_air_threat_is_normalized_for_independent_correlation():
    from xml.etree import ElementTree
    root = ElementTree.fromstring(
        '''<?xml version="1.0"?><rss version="2.0"><channel>
        <item><title>В регионе объявлен режим опасности атаки БПЛА</title>
        <pubDate>Sun, 04 Oct 26 12:12:00 +0300</pubDate>
        <link>https://37.mchs.gov.ru/deyatelnost/press-centr/novosti/5836623</link>
        <yandex:full-text xmlns:yandex="http://news.yandex.ru">Оперативная информация.</yandex:full-text></item>
        </channel></rss>'''
    )
    event = list(MchsRssAdapter()._parse(root))[0]
    assert event.event_type == "public_safety.air_threat"
    assert event.category.value == "air_threat"
    assert event.subtype == "drone_warning"
    assert event.severity.value == "critical"
    assert event.payload["source_kind"] == "official_mchs"
    assert event.correlation_key == "region:37:air_threat:drone_warning"


def test_mchs_rss_air_threat_clear_is_typed():
    from xml.etree import ElementTree
    root = ElementTree.fromstring(
        '''<?xml version="1.0"?><rss version="2.0"><channel>
        <item><title>Отбой опасности атаки БПЛА в регионе</title>
        <pubDate>Sun, 04 Oct 26 13:12:00 +0300</pubDate>
        <link>https://37.mchs.gov.ru/deyatelnost/press-centr/novosti/5836624</link>
        </item></channel></rss>'''
    )
    event = list(MchsRssAdapter()._parse(root))[0]
    assert event.resolved is True
    assert event.resolution_type.value == "all_clear"


def test_mchs_and_regional_telegram_are_correlated_and_require_both_clear():
    from datetime import datetime, timezone, timedelta
    from alertsrv.adapters.ivanovo_operational_telegram import parse_telegram_preview
    from alertsrv.engine import AlertEngine
    from xml.etree import ElementTree

    root = ElementTree.fromstring(
        '''<?xml version="1.0"?><rss version="2.0"><channel>
        <item><title>В регионе объявлен режим опасности атаки БПЛА</title>
        <pubDate>Sun, 04 Oct 26 03:00:00 +0300</pubDate>
        <link>https://37.mchs.gov.ru/deyatelnost/press-centr/novosti/5836623</link>
        </item>
        <item><title>Отбой опасности атаки БПЛА в регионе</title>
        <pubDate>Sun, 04 Oct 26 07:00:00 +0300</pubDate>
        <link>https://37.mchs.gov.ru/deyatelnost/press-centr/novosti/5836624</link>
        </item>
        </channel></rss>'''
    )
    mchs_events = list(MchsRssAdapter()._parse(root))
    telegram_events = parse_telegram_preview(
        '''<div class="tgme_widget_message js-widget_message" data-post="ivanovoobl/1"><div class="tgme_widget_message_text">Оперативный штаб: В регионе объявлен режим опасности атаки БПЛА.</div><time datetime="2026-10-04T03:10:00+00:00"></time></div><div class="tgme_widget_message js-widget_message" data-post="ivanovoobl/2"><div class="tgme_widget_message_text">Оперативный штаб: Отбой опасности БПЛА в Ивановской области.</div><time datetime="2026-10-04T07:10:00+00:00"></time></div>''',
        observed_at=datetime(2026, 10, 4, 8, tzinfo=timezone.utc),
        max_age=timedelta(hours=12),
    )
    engine = AlertEngine()
    alert = engine.ingest(mchs_events[0])
    engine.ingest(telegram_events[0])
    assert len(alert.evidence) == 2
    assert alert.state.value == "active"
    engine.ingest(telegram_events[1])
    assert alert.state.value == "active"
    engine.ingest(mchs_events[1])
    assert alert.state.value == "resolved"
