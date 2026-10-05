import unittest

from alertsrv.source_authority import SourceAuthority, source_authority


class SourceAuthorityTests(unittest.TestCase):
    def test_primary_official_sources_are_authoritative(self):
        for kind in (
            "official_regional_operational_hq",
            "official_rosgidromet_hydrology",
            "veterinary_service_npa",
            "official_mchs",
        ):
            policy = source_authority(kind)
            self.assertEqual(policy.authority, SourceAuthority.OFFICIAL_PRIMARY)
            self.assertEqual(policy.score, 1.0)

    def test_official_corroborting_source_is_not_primary(self):
        policy = source_authority("official_civil_defense")
        self.assertEqual(policy.authority, SourceAuthority.OFFICIAL_CORROBORATING)
        self.assertLess(policy.score, 1.0)

    def test_unknown_source_is_not_promoted_by_parser_confidence(self):
        policy = source_authority("unknown-source")
        self.assertEqual(policy.authority, SourceAuthority.UNKNOWN)
        self.assertEqual(policy.score, 0.0)


if __name__ == "__main__":
    unittest.main()
