from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol

from .models import Alert


class DeliveryState(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Notification:
    notification_id: str
    alert_id: str
    channel: str
    title: str
    body: str
    created_at: datetime


@dataclass(slots=True)
class Delivery:
    notification: Notification
    state: DeliveryState = DeliveryState.PENDING
    attempts: int = 0
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: str | None = None


class NotificationAdapter(Protocol):
    channel: str

    def send(self, notification: Notification) -> None:
        ...


class NotificationDispatcher:
    """Dispatch notifications without coupling delivery failure to alert state."""

    def __init__(self) -> None:
        self._deliveries: dict[str, Delivery] = {}

    def dispatch(
        self,
        alert: Alert,
        *,
        adapters: list[NotificationAdapter] | tuple[NotificationAdapter, ...],
        body: str | None = None,
        now: datetime | None = None,
    ) -> list[Delivery]:
        created_at = now or datetime.now(timezone.utc)
        message_id = f"{alert.alert_id}:{created_at.isoformat()}"
        results: list[Delivery] = []
        for adapter in adapters:
            channel = adapter.channel
            notification = Notification(
                notification_id=f"{message_id}:{channel}",
                alert_id=alert.alert_id,
                channel=channel,
                title=alert.title,
                body=body or alert.title,
                created_at=created_at,
            )
            delivery = Delivery(notification=notification, updated_at=created_at)
            self._deliveries[notification.notification_id] = delivery
            try:
                delivery.attempts += 1
                adapter.send(notification)
            except Exception as exc:
                delivery.state = DeliveryState.FAILED
                delivery.error = str(exc)
            else:
                delivery.state = DeliveryState.SENT
                delivery.error = None
            delivery.updated_at = datetime.now(timezone.utc)
            results.append(delivery)
        return results

    def get(self, notification_id: str) -> Delivery | None:
        return self._deliveries.get(notification_id)

    def all(self) -> tuple[Delivery, ...]:
        return tuple(self._deliveries.values())
