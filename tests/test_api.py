import json
import unittest
from urllib.request import Request, urlopen

from alertsrv.api import create_server
from alertsrv.engine import AlertEngine
from alertsrv.service import AlertService
from tests.test_engine import event


class APITests(unittest.TestCase):
    def setUp(self):
        self.server = create_server(AlertService(AlertEngine()))
        self.thread = __import__("threading").Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def get(self, path):
        with urlopen(self.base + path, timeout=2) as response:
            return response.status, json.load(response)

    def test_health(self):
        status, body = self.get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "ok"})

    def test_alert_list_and_detail(self):
        alert = self.server.RequestHandlerClass.service.accept(event("1", "weather-a"))
        status, body = self.get("/api/v1/alerts")
        self.assertEqual(status, 200)
        self.assertEqual(body["alerts"][0]["alert_id"], alert.alert_id)

        status, body = self.get(f"/api/v1/alerts/{alert.alert_id}")
        self.assertEqual(status, 200)
        self.assertEqual(body["state"], "active")

    def test_unknown_alert_returns_404(self):
        try:
            self.get("/api/v1/alerts/not-found")
        except Exception as exc:
            self.assertEqual(exc.code, 404)
            self.assertEqual(json.load(exc), {"error": "alert not found"})
        else:
            self.fail("expected HTTP 404")
