from __future__ import annotations

import json
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .models import AlertState, Severity
from .serialization import alert_to_dict
from .service import AlertService


class AlertAPIHandler(BaseHTTPRequestHandler):
    service: AlertService | None = None

    def _send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.service is None:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "service unavailable"})
            return
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if path == "/api/v1/alerts":
            alerts = self.service.all()
            self._send_json(HTTPStatus.OK, {"alerts": [alert_to_dict(a) for a in alerts]})
            return
        if path.startswith("/api/v1/alerts/"):
            alert_id = path.rsplit("/", 1)[-1]
            try:
                alert = self.service.engine.get(alert_id)
            except KeyError:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "alert not found"})
                return
            self._send_json(HTTPStatus.OK, alert_to_dict(alert))
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self) -> None:
        if self.service is None:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "service unavailable"})
            return
        path = urlparse(self.path).path
        if path == "/api/v1/alerts/expire":
            expired = self.service.expire()
            self._send_json(HTTPStatus.OK, {"expired": [alert_to_dict(a) for a in expired]})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def log_message(self, format: str, *args: object) -> None:
        return


def create_server(service: AlertService, host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    class Handler(AlertAPIHandler):
        pass

    Handler.service = service
    return ThreadingHTTPServer((host, port), Handler)
