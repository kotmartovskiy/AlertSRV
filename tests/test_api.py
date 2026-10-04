import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from alertsrv.api import create_server
from alertsrv.engine import AlertEngine
from alertsrv.service import AlertService
from tests.test_engine import event


class APITests(unittest.TestCase):
    def setUp(self):
        self.server = create_server(AlertService(AlertEngine()))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = Request(self.base + path, data=data, method=method)
        if data is not None:
            request.add_header("Content-Type", "application/json")
        return urlopen(request, timeout=2)

    def get(self, path):
        with self.request("GET", path) as response:
            return response.status, json.load(response)

    def test_health(self):
        status, body = self.get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "ok"})

    def test_list_alerts_by_state_and_sources(self):
        source = event("state-filter", "weather-a")
        payload = {
            "event_id": source.event_id, "source_id": source.source_id, "event_type": source.event_type,
            "title": source.title, "severity": source.severity.value, "confidence": source.confidence,
            "occurred_at": source.occurred_at.isoformat(), "received_at": source.received_at.isoformat(),
            "correlation_key": source.correlation_key,
        }
        with self.request("POST", "/api/v1/events", payload):
            pass
        status, active = self.get("/api/v1/alerts?state=active")
        self.assertEqual(status, 200)
        self.assertEqual(len(active["alerts"]), 1)
        status, sources = self.get("/api/v1/sources")
        self.assertEqual(status, 200)
        self.assertEqual(sources["sources"], {})

    def test_post_event_then_get_alert(self):
        source = event("1", "weather-a")
        payload = {
            "event_id": source.event_id,
            "source_id": source.source_id,
            "event_type": source.event_type,
            "title": source.title,
            "severity": source.severity.value,
            "confidence": source.confidence,
            "occurred_at": source.occurred_at.isoformat(),
            "received_at": source.received_at.isoformat(),
            "correlation_key": source.correlation_key,
            "payload": source.payload,
        }
        with self.request("POST", "/api/v1/events", payload) as response:
            created = json.load(response)
            self.assertEqual(response.status, 200)
        status, listed = self.get("/api/v1/alerts")
        self.assertEqual(status, 200)
        self.assertEqual(listed["alerts"][0]["alert_id"], created["alert_id"])

    def test_duplicate_post_is_idempotent(self):
        source = event("1", "weather-a")
        payload = {
            "event_id": source.event_id,
            "source_id": source.source_id,
            "event_type": source.event_type,
            "title": source.title,
            "severity": source.severity.value,
            "confidence": source.confidence,
            "occurred_at": source.occurred_at.isoformat(),
            "received_at": source.received_at.isoformat(),
            "correlation_key": source.correlation_key,
        }
        with self.request("POST", "/api/v1/events", payload) as response:
            first = json.load(response)
        with self.request("POST", "/api/v1/events", payload) as response:
            second = json.load(response)
        self.assertEqual(first["alert_id"], second["alert_id"])
        self.assertEqual(len(second["evidence"]), 1)

    def test_invalid_event_returns_400(self):
        with self.assertRaises(HTTPError) as ctx:
            self.request("POST", "/api/v1/events", {"event_id": "broken"})
        self.assertEqual(ctx.exception.code, 400)
        self.assertEqual(json.load(ctx.exception), {"error": "missing field: source_id"})

    def test_rejects_naive_datetime(self):
        source = event("naive", "weather-a")
        payload = {
            "event_id": source.event_id, "source_id": source.source_id, "event_type": source.event_type,
            "title": source.title, "severity": source.severity.value, "confidence": source.confidence,
            "occurred_at": source.occurred_at.replace(tzinfo=None).isoformat(),
            "received_at": source.received_at.isoformat(), "correlation_key": source.correlation_key,
        }
        with self.assertRaises(HTTPError) as ctx:
            self.request("POST", "/api/v1/events", payload)
        self.assertEqual(ctx.exception.code, 400)
        self.assertIn("timezone", json.load(ctx.exception)["error"])

    def test_rejects_non_object_payload(self):
        source = event("payload", "weather-a")
        payload = {
            "event_id": source.event_id, "source_id": source.source_id, "event_type": source.event_type,
            "title": source.title, "severity": source.severity.value, "confidence": source.confidence,
            "occurred_at": source.occurred_at.isoformat(), "received_at": source.received_at.isoformat(),
            "correlation_key": source.correlation_key, "payload": ["bad"],
        }
        with self.assertRaises(HTTPError) as ctx:
            self.request("POST", "/api/v1/events", payload)
        self.assertEqual(ctx.exception.code, 400)
        self.assertEqual(json.load(ctx.exception), {"error": "payload must be an object"})

    def test_unknown_alert_returns_404(self):
        with self.assertRaises(HTTPError) as ctx:
            self.request("GET", "/api/v1/alerts/not-found")
        self.assertEqual(ctx.exception.code, 404)
        self.assertEqual(json.load(ctx.exception), {"error": "alert not found"})


if __name__ == "__main__":
    unittest.main()
