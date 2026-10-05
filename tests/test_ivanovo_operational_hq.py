import unittest
from datetime import datetime, timezone

from alertsrv.adapters.ivanovo_operational_hq import (
    IvanovoOperationalHQAdapter,
    parse_operational_page,
)
from alertsrv.engine import AlertEngine

UTC = timezone.utc


class IvanovoOperationalHQTests(unittest.TestCase):
    def test_warning_and_clear_are_sorted_oldest_first(self):
        html = '''
        <html><head>
        <title>Информация оперативного штаба Ивановской области</title>
        <meta name="description" content="Обновление по состоянию на 06:33: Отбой опасности БПЛА в Ивановской области.
        Обновление по состоянию на 05:40: В регионе сохраняется режим опасности БПЛА.
        ">
        </head></html>
        '''
        events = parse_operational_page(
            html,
            url="https://ivanovoobl.ru/press?id=77121&type=news",
            observed_at=datetime(2026, 10, 5, 6, 40, tzinfo=UTC),
        )
        self.assertEqual(len(events), 2)
        self.assertFalse(events[0].resolved)
        self.assertTrue(events[1].resolved)
        self.assertEqual(events[0].payload["subtype"], "drone_warning")
        self.assertEqual(events[1].payload["subtype"], "drone_warning")
        self.assertEqual(events[0].correlation_key, events[1].correlation_key)

    def test_engine_resolves_warning_when_page_is_replayed(self):
        html = '''
        <html><head>
        <title>Информация оперативного штаба Ивановской области</title>
        <meta name="description" content="Обновление по состоянию на 06:33: Отбой опасности БПЛА в Ивановской области.
        Обновление по состоянию на 05:40: В регионе сохраняется режим опасности БПЛА.">
        </head></html>
        '''
        events = parse_operational_page(
            html,
            url="https://ivanovoobl.ru/?id=77121&type=news",
            observed_at=datetime(2026, 10, 5, 6, 40, tzinfo=UTC),
        )
        engine = AlertEngine()
        alert = engine.ingest(events[0])
        self.assertEqual(alert.state.value, "active")
        resolved = engine.ingest(events[1])
        self.assertIs(alert, resolved)
        self.assertEqual(alert.state.value, "resolved")

    def test_generic_attack_report_is_not_air_warning(self):
        html = '''
        <html><head>
        <title>Оперативный штаб. Ивановская область</title>
        <meta name="description" content="Отбита атака БПЛА. Пострадавших нет.">
        </head></html>
        '''
        self.assertEqual(
            parse_operational_page(
                html,
                url="https://ivanovoobl.ru/?id=77142&type=news",
                observed_at=datetime(2026, 10, 5, 7, 0, tzinfo=UTC),
            ),
            [],
        )

    def test_missile_warning(self):
        html = '''
        <html><head>
        <title>Информация оперативного штаба Ивановской области</title>
        <meta name="description" content="Объявлена ракетная опасность.">
        </head></html>
        '''
        events = parse_operational_page(
            html,
            url="https://ivanovoobl.ru/?id=123&type=news",
            observed_at=datetime(2026, 10, 5, 7, 0, tzinfo=UTC),
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["subtype"], "missile_warning")
        self.assertFalse(events[0].resolved)

    def test_explicit_local_time_keeps_moscow_timezone_semantics(self):
        html = """<html><head><title>Информация оперативного штаба Ивановской области</title>
        <meta name="description" content="Обновление по состоянию на 06:33: Опасность БПЛА в Ивановской области.">
        </head></html>"""
        events = parse_operational_page(
            html,
            url="https://ivanovoobl.ru/?id=77123&type=news",
            observed_at=datetime(2026, 10, 5, 3, 40, tzinfo=UTC),
        )
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].occurred_at, datetime(2026, 10, 5, 3, 33, tzinfo=UTC))

    def test_sitemap_index_reads_all_child_sitemaps(self):
        class FakeAdapter(IvanovoOperationalHQAdapter):
            def _fetch(self, url):
                if url == "https://example.test/index.xml":
                    return b"""<?xml version="1.0"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>https://example.test/a.xml</loc></sitemap><sitemap><loc>https://example.test/b.xml</loc></sitemap></sitemapindex>"""
                return {
                    "https://example.test/a.xml": b"""<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.test/old</loc><lastmod>2099-01-01T00:00:00+00:00</lastmod></url></urlset>""",
                    "https://example.test/b.xml": b"""<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.test/new</loc><lastmod>2099-01-02T00:00:00+00:00</lastmod></url></urlset>""",
                }[url]

        adapter = FakeAdapter("https://example.test/index.xml")
        rows = adapter._sitemap_urls()
        self.assertEqual([url for url, _ in rows], ["https://example.test/new", "https://example.test/old"])

    def test_adapter_exposes_source_id(self):
        adapter = IvanovoOperationalHQAdapter()
        self.assertEqual(adapter.source_id, "ivanovo-operational-hq")


if __name__ == "__main__":
    unittest.main()
