from datetime import datetime, timedelta, timezone

from alertsrv.adapters.rosgidromet import _EmergencyParser, RosgidrometEmergencyAdapter, RosgidrometHydrologyAdapter


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


def test_hydrology_parser_preserves_structured_row():
    html = """
    <h1>Опасные и неблагоприятные явления на реках</h1>
    <div>15 июля 2026 г</div>
    <table>
      <tr><th>Субъект РФ</th><th>Водные объекты</th><th>Пункт</th><th>Факт</th><th>Прогноз на трое суток</th></tr>
      <tr><td>Ивановская область</td><td>Уводь</td><td>г. Иваново</td>
          <td>превышена отметка опасного явления (ОЯ)</td>
          <td>превышение отметки опасного явления будет сохраняться</td></tr>
    </table>
    """
    events = RosgidrometHydrologyAdapter(max_bulletin_age=timedelta(days=100)).parse(
        html,
        url="https://www.meteorf.gov.ru/test",
        received_at=datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc),
    )
    assert len(events) == 1
    event = events[0]
    assert event.severity.value == "critical"
    assert event.payload["region_name"] == "Ивановская область"
    assert event.payload["water_body"] == "Уводь"
    assert event.payload["observation_point"] == "г. Иваново"
    assert event.payload["category"] == "hydrology"
    assert event.payload["subtype"] == "dangerous"


def test_hydrology_unfavorable_is_warning():
    html = """
    <div>7 августа 2026 г</div>
    <table><tr><td>Костромская область</td><td>Волга</td><td>Кострома</td>
    <td>превышена отметка НЯ</td><td>сохранится</td></tr></table>
    """
    events = RosgidrometHydrologyAdapter(max_bulletin_age=timedelta(days=100)).parse(
        html, url="https://example.test/h", received_at=datetime(2026, 8, 7, tzinfo=timezone.utc)
    )
    assert len(events) == 1
    assert events[0].severity.value == "warning"
    assert events[0].payload["subtype"] == "unfavorable"


def test_hydrology_ignores_old_bulletin():
    html = """<div>15 июля 2026 г</div><table><tr><td>Ивановская область</td><td>Уводь</td><td>Иваново</td><td>превышена отметка ОЯ</td><td>сохранится</td></tr></table>"""
    events = RosgidrometHydrologyAdapter().parse(
        html, url="https://example.test/old", received_at=datetime(2026, 10, 5, tzinfo=timezone.utc)
    )
    assert events == []
