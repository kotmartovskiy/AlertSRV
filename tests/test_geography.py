import unittest

from alertsrv.geography import AffectedArea, GeographyLevel, area_from_dict, area_to_dict, areas_compatible


class GeographyTests(unittest.TestCase):
    def test_each_hierarchy_level_has_identity(self):
        areas = [
            AffectedArea(GeographyLevel.FEDERAL, name="Россия"),
            AffectedArea(GeographyLevel.REGION, name="Ивановская область", code="37"),
            AffectedArea(GeographyLevel.MUNICIPALITY, name="Лежневский район"),
            AffectedArea(
                GeographyLevel.SETTLEMENT,
                name="д. Кунятиха",
                parent_name="Лежневский район",
            ),
            AffectedArea(
                GeographyLevel.LOCAL_AREA,
                name="Хозяйство",
                cadastral_number="37:09:010338:245",
                parent_name="Лежневский район",
            ),
        ]
        self.assertEqual([a.rank for a in areas], [0, 1, 2, 3, 4])
        self.assertEqual(len({a.identity() for a in areas}), 5)

    def test_settlement_requires_parent(self):
        with self.assertRaises(ValueError):
            AffectedArea(GeographyLevel.SETTLEMENT, name="д. Кунятиха")

    def test_local_area_requires_parent(self):
        with self.assertRaises(ValueError):
            AffectedArea(GeographyLevel.LOCAL_AREA, name="Хозяйство")

    def test_farm_is_backward_compatible_local_area(self):
        area = area_from_dict(
            {
                "level": "farm",
                "name": "Хозяйство",
                "cadastral_number": "37:09:010338:245",
                "district": "Лежневский район",
            }
        )
        self.assertEqual(area.level, GeographyLevel.LOCAL_AREA)
        self.assertEqual(area.parent_name, "Лежневский район")

    def test_round_trip_preserves_typed_identity(self):
        original = AffectedArea(
            GeographyLevel.SETTLEMENT,
            name="д. Кунятиха",
            parent_name="Лежневский район",
        )
        self.assertEqual(
            area_to_dict(area_from_dict(area_to_dict(original))),
            area_to_dict(original),
        )

    def test_only_equal_level_identity_is_compatible(self):
        municipality = AffectedArea(GeographyLevel.MUNICIPALITY, name="Лежневский район")
        same = AffectedArea(GeographyLevel.MUNICIPALITY, name="Лежневский район")
        settlement = AffectedArea(
            GeographyLevel.SETTLEMENT,
            name="д. Кунятиха",
            parent_name="Лежневский район",
        )
        self.assertTrue(areas_compatible(municipality, same))
        self.assertFalse(areas_compatible(municipality, settlement))


if __name__ == "__main__":
    unittest.main()
