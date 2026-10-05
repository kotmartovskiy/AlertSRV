import unittest

from alertsrv.source_catalog import (
    IVANOVO,
    get_regional_government_source,
    list_regional_government_sources,
)


class SourceCatalogTests(unittest.TestCase):
    def test_ivanovo_is_authoritative_https_source(self):
        source = get_regional_government_source("37")
        self.assertIs(source, IVANOVO)
        self.assertEqual(source.region_name, "Ивановская область")
        self.assertTrue(source.base_url.startswith("https://"))
        self.assertEqual(source.source_id, "ivanovo-operational-hq")

    def test_unknown_region_is_not_silently_invented(self):
        with self.assertRaises(KeyError):
            get_regional_government_source("00")

    def test_catalog_is_deterministic(self):
        self.assertEqual(list_regional_government_sources(), (IVANOVO,))


if __name__ == "__main__":
    unittest.main()
