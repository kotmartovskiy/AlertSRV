# Sensor / Telemetry Service concept

Status: architectural decision, implementation deferred.

Sensor and telemetry infrastructure belongs to the LAN Discovery ecosystem, but it is deliberately kept outside AlertSRV.

The Sensor/Telemetry Service answers: what is measured, what physical/device state exists, and how healthy is the source?

AlertSRV answers: does an observed event constitute a meaningful alert, and what is the alert lifecycle?

## Layering

LAN Discovery Platform
- Discovery
- Sensor / Telemetry Service
  - adapters: MQTT, Zigbee, BLE, Modbus, GPIO, HTTP, SNMP, custom
  - device registry
  - sensor registry
  - measurements
  - states
  - source/device health
  - calibration
  - units
- Services
  -> events
  -> AlertSRV
  -> Automation Engine
  -> Notification

This is a target architecture, not a requirement to implement an event bus now.

## Conceptual data flow

Measurement -> State / Condition -> Event -> Alert -> Notification

Not every measurement is an event, and not every event is an alert.

Example:
- temperature = 23.4 C -> measurement
- temperature > configured threshold -> condition
- threshold crossed -> event
- sustained overheat / correlated with another signal -> alert
- alert delivered to a user or automation -> notification

## Scope of the future Sensor / Telemetry Service

The service should be broad enough to support:
- home/security sensors
- weather stations
- LAN Discovery hardware telemetry: CPU temperature, RAM/storage state, SMART, network/link state
- equipment telemetry: temperature, pressure, current, motor state, fault codes
- industrial/legacy equipment where practical

It should preserve raw measurements and source identity instead of converting everything into alerts.

## Relationship with AlertSRV

AlertSRV should consume normalized events from the telemetry layer just like it consumes events from weather, emergency-warning, camera-analysis, or other adapters.

Important separation:
- Sensor/Telemetry Service owns measurement semantics, units, device/sensor identity, calibration and source health.
- AlertSRV owns alert semantics: deduplication, correlation, severity, confidence, lifecycle, persistence and alert-facing API.
- A sensor source outage must not automatically mean that a physical alarm is resolved.
- A measurement becoming normal does not necessarily resolve an alert unless an explicit resolution event/policy says so.

## Architectural rule

Do not move sensor registry, measurements, calibration or device telemetry into AlertSRV merely because AlertSRV consumes sensor events.

Boundary: telemetry describes reality; AlertSRV manages meaningful alerts about that reality.

## Deferred decisions

Intentionally not fixed yet:
- exact Sensor/Telemetry Service API
- persistent measurement schema
- event transport / event bus
- MQTT topic conventions
- device identity model
- retention policy for high-frequency telemetry
- calibration model
- geographic metadata
- rules engine placement

These should be decided when the first real telemetry source is implemented.

## Implementation order

1. Finish and stabilize AlertSRV lifecycle/persistence/API semantics.
2. Define the minimal event contract between telemetry and AlertSRV.
3. Build Sensor/Telemetry Service as a separate module/service.
4. Add real sensor adapters.
5. Add automation and notification layers later.

This document records the architectural decision so future work can resume without reconstructing the reasoning.
