import unittest

from alertsrv.regions.base import RegionModule, RegionSourceSpec
from alertsrv.regions.ivanovo import IVANOVO_REGION


class RegionModuleTests(unittest.TestCase):
    def test_ivanovo_is_explicitly_scoped(self):
        self.assertEqual(IVANOVO_REGION.region_code, "37")
        self.assertEqual(IVANOVO_REGION.timezone, "Europe/Moscow")
        self.assertEqual(
            IVANOVO_REGION.source_ids(),
            (
                "ivanovo-operational-hq",
                "ivanovo-operational-telegram",
                "mchs-ivanovo",
                "ivanovo-veterinary-registry",
            ),
        )

    def test_sources_are_lazy_and_instantiated_only_for_selected_region(self):
        calls = []

        def factory():
            calls.append("created")
            return object()

        region = RegionModule(
            region_code="99",
            region_name="Test",
            timezone="Europe/Moscow",
            sources=(
                RegionSourceSpec(
                    source_id="test-source",
                    interval_seconds=60,
                    categories=frozenset({"test"}),
                    factory=factory,
                ),
            ),
        )
        self.assertEqual(calls, [])
        created = region.create_sources()
        self.assertEqual(calls, ["created"])
        self.assertEqual(len(created), 1)

    def test_each_source_has_a_bounded_poll_interval(self):
        self.assertTrue(all(source.interval_seconds > 0 for source in IVANOVO_REGION.sources))

    def test_duplicate_source_ids_are_rejected(self):
        def factory():
            return object()

        with self.assertRaises(ValueError):
            RegionModule(
                region_code="99",
                region_name="Test",
                timezone="Europe/Moscow",
                sources=(
                    RegionSourceSpec("same", 60, frozenset(), factory),
                    RegionSourceSpec("same", 60, frozenset(), factory),
                ),
            )


if __name__ == "__main__":
    unittest.main()
