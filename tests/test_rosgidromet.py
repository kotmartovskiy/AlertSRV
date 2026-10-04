from datetime import datetime, timezone

from alertsrv.adapters.rosgidromet import _EmergencyParser, RosgidrometEmergencyAdapter


def test_parser_extracts_emergency_items():
    html = """
    <div class="item">
      <div class="date"><div class="in">5 октября 2026 [12:30]</div></div>
      <div class="text"><div class="in">Опасное явление: сильный ветер.</div></div>
    </div>
    """
    parser = _EmergencyParser()
    parser.feed(html)
    assert parser.items == [
        ("5 октября 2026 [12:30]", "Опасное явление: сильный ветер.")
    ]


def test_adapter_date_parser():
    value = RosgidrometEmergencyAdapter._parse_date("5 октября 2026 [12:30]")
    assert value == datetime(2026, 10, 5, 12, 30, tzinfo=timezone.utc)


def test_adapter_has_national_scope():
    adapter = RosgidrometEmergencyAdapter()
    assert adapter.source_id == "rosgidromet-emergency"
