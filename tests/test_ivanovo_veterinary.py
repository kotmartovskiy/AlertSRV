import unittest
from datetime import datetime, timezone
from alertsrv.adapters.ivanovo_veterinary import parse_registry_html, IvanovoVeterinaryRegistryAdapter

UTC = timezone.utc
BASE = "https://vet.ivanovoobl.ru/pravovye-akty/"

class IvanovoVeterinaryTests(unittest.TestCase):
    def test_establishment_key(self):
        html = '<a href="/doc/14.pdf">Приказ службы ветеринарии Ивановской области от 24.04.2026 № 14-од "Об установлении ограничительных мероприятий (карантина) по лейкозу крупного рогатого скота на территории Ивановской области"</a>'
        e = parse_registry_html(html, registry_url=BASE, observed_at=datetime(2026,10,5,tzinfo=UTC))[0]
        self.assertEqual(e.payload["disease"], "leukosis")
        self.assertEqual(e.payload["document_number"], "14-од")
        self.assertFalse(e.resolved)
        self.assertIn("order:14-од", e.correlation_key)

    def test_cancellation_targets_referenced_order(self):
        html = '<a href="/doc/19.pdf">Приказ службы ветеринарии Ивановской области от 13.05.2026 № 19-од "Об отмене ограничительных мероприятий (карантина) по лейкозу крупного рогатого скота на территории Ивановской области и внесении изменений в приказ службы ветеринарии Ивановской области от 24.05.2022 № 35-од"</a>'
        e = parse_registry_html(html, registry_url=BASE, observed_at=datetime(2026,10,5,tzinfo=UTC))[0]
        self.assertTrue(e.resolved)
        self.assertIn("order:35-од", e.correlation_key)

    def test_generic_cancellation_is_not_resolution(self):
        html = '<a href="/doc/34.pdf">Приказ службы ветеринарии Ивановской области от 08.09.2026 № 34-од "Об отмене ограничительных мероприятий (карантина) по заразному узелковому дерматиту крупного рогатого скота на территории Ивановской области"</a>'
        e = parse_registry_html(html, registry_url=BASE, observed_at=datetime(2026,10,5,tzinfo=UTC))[0]
        self.assertFalse(e.resolved)
        self.assertTrue(e.payload["resolved"])

    def test_non_quarantine_ignored(self):
        html = '<a href="/doc/30.pdf">Приказ № 30-од "О противоэпизоотической комиссии"</a>'
        self.assertEqual(parse_registry_html(html, registry_url=BASE, observed_at=datetime.now(UTC)), [])

    def test_source(self):
        self.assertEqual(IvanovoVeterinaryRegistryAdapter().source_id, "ivanovo-veterinary-registry")

if __name__ == "__main__":
    unittest.main()
