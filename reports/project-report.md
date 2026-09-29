# Cloud-Connected Smart Plant Care and Watering System

## Abstract

This project demonstrates an IoT-to-cloud pattern using synthetic sensor data. A virtual plant sends timestamped soil moisture, temperature, humidity and light measurements to a REST service. The service validates and stores measurements, evaluates watering rules, tracks alerts and presents current state and history on a browser dashboard. The local version requires no sensors or pump.

## Problem statement

Manual watering can be inconsistent, and plant conditions are hard to monitor when the user is away. The project explores how connected sensors, remote storage and configurable rules could support more consistent monitoring. It is a course demonstration; it does not claim measured plant growth or water savings.

## Objectives

- Model sensor-to-service communication with a Python virtual device.
- Validate and persist time-series readings.
- Demonstrate automated threshold decisions, cooldown and manual actions.
- Show status, alerts and historical readings in a dashboard.
- Document how local components map to cloud services and optional hardware.

## Architecture and tools

The simulator posts JSON over HTTP to FastAPI. Pydantic validates payload ranges. The backend stores devices, sensor readings, watering events and alerts in SQLite for local use; it can use PostgreSQL through `DATABASE_URL` and psycopg when configured. The dashboard polls API endpoints every five seconds and plots recent readings. The actuator remains virtual.

## Data and automation

Each reading includes a device ID, soil moisture percent, air temperature in Celsius, relative humidity, light percent and UTC timestamp. Soil values gradually decline in simulation. When moisture falls below the device threshold, the backend checks the automatic-water setting and cooldown, then records a bounded virtual event. A later simulator sample reflects higher moisture. Low moisture, high temperature and a missed heartbeat can create alerts.

## Security and scale

Human accounts use scrypt password hashes and expiring database-backed sessions. Dashboard routes require the session and verify plant ownership. Sensor ingestion separately uses a device API key and input validation; the shipped key is only a local demo credential. A public deployment still needs unique per-device secrets, HTTPS, managed secret storage, request limits, logging, managed backups and retention. High-volume deployments should add an API gateway, queue, stateless workers, managed time-series storage, autoscaling and aggregation.

## Evaluation and test evidence

The automated suite covers API validation, persistence, thresholds, cooldown, manual and automatic virtual actions, alerts, device status, multiple devices and database failure handling. A manual test plan is in `../docs/test_plan.md`. Record execution results after running `python -m pytest`; no unobserved test outcome is claimed here.

## Limitations

No physical ESP32, sensors or pump were used. The local SQLite mode is not suitable as shared storage for scaled cloud instances. The PostgreSQL adapter is included but requires a configured managed database and has not been validated against a provider account. Cloud hosting, notifications, a deployed CI/CD pipeline and screenshots from a hosted service are not included.

## Future work

Connect a managed PostgreSQL service and exercise the migration; deploy a secured cloud service after a hosting plan is selected; add notification delivery and CI/CD; collect genuine screenshots and deployment evidence; then test optional ESP32 hardware using isolated low-voltage components and independent pump safety cutoffs.
