# AlertSRV HTTP API contract

The API is a local integration boundary. It accepts already-normalized events; source-specific parsing belongs in adapters.

## Endpoints

- `GET /health` -> `200 {"status":"ok"}`
- `GET /api/v1/alerts` -> `200 {"alerts":[...]}`
- `GET /api/v1/alerts/<id>` -> alert or `404`
- `POST /api/v1/events` -> accepted alert or `400` for invalid input
- `POST /api/v1/alerts/expire` -> applies configured expiration and returns expired alerts

The default server binds to `127.0.0.1`. Do not expose it to an untrusted network without authentication and access control.

## Event schema

Required fields:

| Field | Type | Rules |
|---|---|---|
| `event_id` | string | stable identifier within a source |
| `source_id` | string | source/adapter identifier |
| `event_type` | string | normalized event type |
| `severity` | string | `INFO`, `WARNING`, or `CRITICAL` |
| `confidence` | number | 0..1; boolean is not accepted |
| `occurred_at` | ISO-8601 datetime | timezone required |
| `received_at` | ISO-8601 datetime | timezone required |
| `correlation_key` | string | adapter-supplied logical correlation key |

Optional fields:

- `title`: string, defaults to empty string.
- `payload`: JSON object, defaults to `{}`.
- `expires_at`: ISO-8601 datetime with timezone, or `null`/omitted.
- `resolved`: boolean, defaults to `false`.

Datetime values must carry explicit timezone information, e.g. `2026-10-04T20:00:00+03:00` or `2026-10-04T17:00:00Z`.

## Error behavior

Malformed JSON, missing fields, wrong types, invalid enum values, invalid datetimes, naive datetimes and model validation failures return HTTP `400` with an object of the form:

```json
{"error":"..."}
```

Unknown routes return `404`.

## Idempotence

Submitting the same source event more than once is expected to be idempotent. The core deduplicates by source/event identity and persists the mapping with the alert update transaction.

## Architectural boundary

This API must not contain source-specific scraping, network polling, geographic correlation or notification delivery. Those belong to adapters or later output layers. The API is intentionally thin.
