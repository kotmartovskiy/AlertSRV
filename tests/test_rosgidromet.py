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



def test_hydrology_fetch_marks_old_latest_bulletin_stale():
    index_html = """
    <a href="/old">Опасные и неблагоприятные явления на реках, озерах и водохранилищах Российской Федерации по состоянию на 15 июля 2026 г.</a>
    """
    adapter = RosgidrometHydrologyAdapter(max_bulletin_age=timedelta(days=1))
    adapter._fetch = lambda url: index_html.encode("utf-8")

    result = adapter.fetch()

    assert result.events == ()
    assert result.stale is True
    assert "old" in result.detail


def test_hydrology_fetch_wraps_current_events():
    index_html = """
    <a href="/current">Опасные и неблагоприятные явления на реках, озерах и водохранилищах Российской Федерации по состоянию на 5 октября 2026 г.</a>
    """
    bulletin_html = """
    <div>5 октября 2026 г</div>
    <table><tr><td>Ивановская область</td><td>Уводь</td><td>Иваново</td>
    <td>превышена отметка ОЯ</td><td>сохранится</td></tr></table>
    """
    adapter = RosgidrometHydrologyAdapter(max_bulletin_age=timedelta(days=7))
    adapter._fetch = lambda url: (index_html if url == adapter.url else bulletin_html).encode("utf-8")

    result = adapter.fetch()

    assert result.stale is False
    assert len(result.events) == 1
    assert result.events[0].source_id == adapter.source_id


def test_hydrology_discovery_selects_latest_matching_bulletin():
    html = """
    <div>2 октября 2026</div>
    <a href="/press/polovod2026/45214/">Опасные и неблагоприятные явления на реках, озерах и водохранилищах Российской Федерации по состоянию на 2 октября 2026 г.</a>
    <a href="/press/polovod2026/45199/">Гидрологическая обстановка на реках Томской области по спутниковым данным за 28 сентября-1 октября 2026 г.</a>
    <a href="/press/polovod2026/45150/">Опасные и неблагоприятные явления на реках, озерах и водохранилищах Российской Федерации по состоянию на 30 сентября 2026 г.</a>
    """
    bulletin = RosgidrometHydrologyAdapter.discover_latest(
        html, now=datetime(2026, 10, 5, tzinfo=timezone.utc)
    )
    assert bulletin is not None
    assert bulletin.url.endswith("/45214/")
    assert bulletin.published_at == datetime(2026, 10, 2, tzinfo=timezone(timedelta(hours=3)))


def test_hydrology_discovery_rejects_future_bulletin():
    html = """
    <a href="/press/polovod2026/45299/">Опасные и неблагоприятные явления на реках, озерах и водохранилищах Российской Федерации по состоянию на 6 октября 2026 г.</a>
    """
    bulletin = RosgidrometHydrologyAdapter.discover_latest(
        html, now=datetime(2026, 10, 5, 12, tzinfo=timezone.utc)
    )
    assert bulletin is None


def test_hydrology_expiration_uses_explicit_forecast_end():
    html = """
    <div>2 октября 2026 г</div>
    <table><tr><td>Ивановская область</td><td>Уводь</td><td>Иваново</td>
    <td>уровень воды ниже отметки поймы</td><td>выход воды на пойму 2-5 октября</td></tr></table>
    """
    events = RosgidrometHydrologyAdapter(max_bulletin_age=timedelta(days=100)).parse(
        html, url="https://example.test/h", received_at=datetime(2026, 10, 2, tzinfo=timezone.utc)
    )
    assert len(events) == 1
    assert events[0].expires_at == datetime(
        2026, 10, 5, 23, 59, 59, tzinfo=timezone(timedelta(hours=3))
    )


def test_hydrology_keeps_open_ended_forecast_without_invented_expiry():
    html = """
    <div>2 октября 2026 г</div>
    <table><tr><td>Ивановская область</td><td>Уводь</td><td>Иваново</td>
    <td>превышена отметка ОЯ</td><td>превышение отметки ОЯ сохранится</td></tr></table>
    """
    events = RosgidrometHydrologyAdapter(max_bulletin_age=timedelta(days=100)).parse(
        html, url="https://example.test/h", received_at=datetime(2026, 10, 2, tzinfo=timezone.utc)
    )
    assert len(events) == 1
    assert events[0].expires_at is None
