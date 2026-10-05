from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from .models import Alert, AlertState, Evidence, Severity


def datetime_to_json(value: datetime) -> str:
    return value.isoformat()


def datetime_from_json(value: str) -> datetime:
    return datetime.fromisoformat(value)


def alert_to_dict(alert: Alert) -> dict[str, Any]:
    return {
        "alert_id": alert.alert_id,
        "correlation_key": alert.correlation_key,
        "state": alert.state.value,
        "severity": alert.severity.value,
        "confidence": alert.confidence,
        "title": alert.title,
        "started_at": datetime_to_json(alert.started_at),
        "updated_at": datetime_to_json(alert.updated_at),
        "expires_at": datetime_to_json(alert.expires_at) if alert.expires_at else None,
        "source_authority": alert.source_authority,
        "source_authority_score": alert.source_authority_score,
        "superseded_by": alert.superseded_by,
        "supersedes_alert_id": alert.supersedes_alert_id,
        "evidence": [
            {
                "event_id": item.event_id,
                "source_id": item.source_id,
                "severity": item.severity.value,
                "confidence": item.confidence,
                "occurred_at": datetime_to_json(item.occurred_at),
                "received_at": datetime_to_json(item.received_at),
                "title": item.title,
                "payload": item.payload,
                "source_authority": item.source_authority,
                "source_authority_score": item.source_authority_score,
            }
            for item in alert.evidence
        ],
        "transition_history": [
            {
                "from": old.value,
                "to": new.value,
                "at": datetime_to_json(at),
                "reason": reason,
            }
            for old, new, at, reason in alert.transition_history
        ],
    }


def alert_from_dict(data: dict[str, Any]) -> Alert:
    evidence = [
        Evidence(
            event_id=item["event_id"],
            source_id=item["source_id"],
            severity=Severity(item["severity"]),
            confidence=float(item["confidence"]),
            occurred_at=datetime_from_json(item["occurred_at"]),
            received_at=datetime_from_json(item["received_at"]),
            title=item["title"],
            payload=dict(item.get("payload", {})),
            source_authority=item.get("source_authority", "unknown"),
            source_authority_score=float(item.get("source_authority_score", 0.0)),
        )
        for item in data.get("evidence", [])
    ]
    transitions = [
        (
            AlertState(item["from"]),
            AlertState(item["to"]),
            datetime_from_json(item["at"]),
            item["reason"],
        )
        for item in data.get("transition_history", [])
    ]
    return Alert(
        alert_id=data["alert_id"],
        correlation_key=data["correlation_key"],
        state=AlertState(data["state"]),
        severity=Severity(data["severity"]),
        confidence=float(data["confidence"]),
        title=data["title"],
        started_at=datetime_from_json(data["started_at"]),
        updated_at=datetime_from_json(data["updated_at"]),
        expires_at=(datetime_from_json(data["expires_at"]) if data.get("expires_at") else None),
        source_authority=data.get("source_authority", "unknown"),
        source_authority_score=float(data.get("source_authority_score", 0.0)),
        superseded_by=data.get("superseded_by"),
        supersedes_alert_id=data.get("supersedes_alert_id"),
        evidence=evidence,
        transition_history=transitions,
    )


def alert_to_json(alert: Alert) -> str:
    return json.dumps(alert_to_dict(alert), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
