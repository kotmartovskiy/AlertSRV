from __future__ import annotations

import json
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .models import NormalizedEvent, Severity
from .serialization import alert_to_dict
from .service import AlertService


def _parse_event(data: dict) -> NormalizedEvent:
    required = ("event_id", "source_id", "event_type", "severity", "confidence", "occurred_at", "received_at", "correlation_key")
    for key in required:
        if key not in data:
            raise ValueError(f"missing field: {key}")
    string_fields = ("event_id", "source_id", "event_type", "title", "correlation_key")
    for key in string_fields:
        if key in data and not isinstance(data[key], str):
            raise ValueError(f"{key} must be a string")
    if "payload" in data and not isinstance(data["payload"], dict):
        raise ValueError("payload must be an object")
    if "resolved" in data and not isinstance(data["resolved"], bool):
        raise ValueError("resolved must be a boolean")
    try:
        confidence = data["confidence"]
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise ValueError("confidence must be a number")
        occurred_at = datetime.fromisoformat(data["occurred_at"])
        received_at = datetime.fromisoformat(data["received_at"])
        expires_at = datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") is not None else None
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid datetime or confidence: {exc}") from exc
    if occurred_at.tzinfo is None or received_at.tzinfo is None or (expires_at is not None and expires_at.tzinfo is None):
        raise ValueError("datetimes must include timezone information")
    return NormalizedEvent(
        event_id=data["event_id"], source_id=data["source_id"], event_type=data["event_type"],
        title=data.get("title", ""), severity=Severity(data["severity"]), confidence=float(confidence),
        occurred_at=occurred_at, received_at=received_at, correlation_key=data["correlation_key"],
        payload=data.get("payload", {}), expires_at=expires_at, resolved=data.get("resolved", False),
    )


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
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/health":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if path == "/api/v1/alerts":
            query = parse_qs(parsed.query)
            state = query.get("state", [None])[0]
            region = query.get("region", [None])[0]
            if state is None:
                alerts = self.service.all()
            else:
                try:
                    from .models import AlertState
                    alerts = self.service.list(AlertState(state))
                except ValueError:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid state"})
                    return
            if region is not None:
                if not region:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid region"})
                    return
                alerts = [
                    a for a in alerts
                    if any(e.payload.get("scope") == "region" and e.payload.get("region_code") == region for e in a.evidence)
                ]
            self._send_json(HTTPStatus.OK, {"alerts": [alert_to_dict(a) for a in alerts]})
            return
        if path == "/api/v1/sources":
            self._send_json(HTTPStatus.OK, {"sources": {k: v.value for k, v in self.service.sources().items()}})
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
                event = _parse_event(data)
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
