import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from alertsrv.adapters.ivanovo_operational_telegram import IvanovoOperationalTelegramAdapter, parse_telegram_preview
from alertsrv.engine import AlertEngine
UTC = timezone.utc
FIXTURE = """
<div class="tgme_widget_message js-widget_message" data-post="ivanovoobl/23556"><div class="tgme_widget_message_text"><b>Оперативный штаб. Ивановская область:</b> В регионе объявлен режим опасности атаки БПЛА.</div><time datetime="2026-10-04T02:46:19+00:00"></time></div>
<div class="tgme_widget_message js-widget_message" data-post="ivanovoobl/23557"><div class="tgme_widget_message_text"><b>Оперативный штаб:</b> Отбой опасности БПЛА в Ивановской области.</div><time datetime="2026-10-04T06:08:11+00:00"></time></div>
"""
class IvanovoOperationalTelegramTests(unittest.TestCase):
    def test_warning_and_clear_are_typed_and_ordered(self):
        events = parse_telegram_preview(FIXTURE, observed_at=datetime(2026,10,4,7,tzinfo=UTC), max_age=timedelta(days=1))
        self.assertEqual(len(events), 2); self.assertFalse(events[0].resolved); self.assertTrue(events[1].resolved)
        self.assertEqual(events[0].subtype, "drone_warning"); self.assertEqual(events[1].resolution_type.value, "all_clear")
        self.assertEqual(events[0].correlation_key, events[1].correlation_key)
    def test_missile_warning_and_clear(self):
        html='<div class="tgme_widget_message js-widget_message" data-post="ivanovoobl/1"><div class="tgme_widget_message_text">Оперативный штаб: объявлена ракетная опасность.</div><time datetime="2026-10-05T06:00:00+00:00"></time></div><div class="tgme_widget_message js-widget_message" data-post="ivanovoobl/2"><div class="tgme_widget_message_text">Оперативный штаб: отбой ракетной опасности.</div><time datetime="2026-10-05T06:20:00+00:00"></time></div>'
        events=parse_telegram_preview(html,observed_at=datetime(2026,10,5,7,tzinfo=UTC),max_age=timedelta(hours=2))
        self.assertEqual([e.subtype for e in events],["missile_warning","missile_warning"]); self.assertFalse(events[0].resolved); self.assertTrue(events[1].resolved)
    def test_irrelevant_post_is_ignored(self):
        html='<div class="tgme_widget_message js-widget_message" data-post="ivanovoobl/3"><div class="tgme_widget_message_text">Новости региона: открыт новый объект.</div><time datetime="2026-10-05T06:00:00+00:00"></time></div>'
        self.assertEqual(parse_telegram_preview(html,observed_at=datetime(2026,10,5,7,tzinfo=UTC),max_age=timedelta(hours=2)),[])
    def test_stale_messages_are_not_active_data(self):
        self.assertEqual(parse_telegram_preview(FIXTURE,observed_at=datetime(2026,10,5,12,tzinfo=UTC),max_age=timedelta(hours=1)),[])
    def test_two_official_sources_require_both_clear_events(self):
        observed=datetime(2026,10,4,7,tzinfo=UTC); telegram=parse_telegram_preview(FIXTURE,observed_at=observed,max_age=timedelta(days=1))
        web=[replace(e,source_id="ivanovo-operational-hq") for e in telegram]
        engine=AlertEngine(); alert=engine.ingest(telegram[0]); engine.ingest(web[0]); self.assertEqual(alert.state.value,"active")
        engine.ingest(telegram[1]); self.assertEqual(alert.state.value,"active")
        engine.ingest(web[1]); self.assertEqual(alert.state.value,"resolved")
    def test_live_channel_old_messages_do_not_become_current_alerts(self):
        result=IvanovoOperationalTelegramAdapter(max_age=timedelta(hours=6)).fetch()
        self.assertEqual(result.events,())
if __name__=="__main__": unittest.main()
