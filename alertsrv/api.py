from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .models import NormalizedEvent, Severity
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

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 1_000_000:
                raise ValueError("invalid content length")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("JSON object required")
            return payload
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError(str(exc)) from exc

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
                alert = self.service.get(alert_id)
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
        if path == "/api/v1/events":
            try:
                data = self._read_json()
                event = NormalizedEvent(
                    event_id=str(data["event_id"]),
                    source_id=str(data["source_id"]),
                    event_type=str(data["event_type"]),
                    title=str(data.get("title", "")),
                    severity=Severity(data["severity"]),
                    confidence=float(data["confidence"]),
                    occurred_at=__import__("datetime").datetime.fromisoformat(data["occurred_at"]),
                    received_at=__import__("datetime").datetime.fromisoformat(data["received_at"]),
                    correlation_key=str(data["correlation_key"]),
                    payload=dict(data.get("payload", {})),
                    expires_at=(
                        __import__("datetime").datetime.fromisoformat(data["expires_at"])
                        if data.get("expires_at") else None
                    ),
                    resolved=bool(data.get("resolved", False)),
                )
                alert = self.service.accept(event)
                self._send_json(HTTPStatus.OK, alert_to_dict(alert))
            except KeyError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc.args[0])})
            except (TypeError, ValueError) as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
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
