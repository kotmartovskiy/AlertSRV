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


def test_mchs_rss_live_smoke():
    # Explicit live smoke test is opt-in so the normal suite remains offline/deterministic.
    import os
    if os.getenv("ALERTSRV_LIVE_MCHS") != "1":
        return
    events = MchsRssAdapter().fetch()
    assert events
