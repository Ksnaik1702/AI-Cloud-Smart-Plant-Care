# Project guide and requirements walkthrough

## 1. What the project does

**Simple view:** the virtual plant sends measurements to a service. The service saves them, checks whether the plant is dry, records a virtual watering action, and shows the result on a dashboard.

**Technical view:** a device adapter sends timestamped JSON over HTTP. FastAPI validates values, SQLite persists device configuration, readings, watering events and alerts, and the browser polls the REST API every five seconds. Replacing the Python adapter with ESP32 firmware keeps the message contract and service boundary the same.

Manual watering can be inconsistent. Historical readings and threshold-based care make changes visible and repeatable. Remote access is a cloud benefit; the local build demonstrates that architecture without requiring an account or physical kit.

Workflow:

```text
Virtual plant -> simulator -> HTTP API -> validation and rules -> database
                                                        |          |
                                                        v          v
                                                  virtual pump   dashboard
```

## 2. Industry use

The same pattern is used in greenhouse and nursery monitoring, precision irrigation, smart-home planters, vertical farms, hydroponics and environmental monitoring. Centralized history helps operators see trends and respond remotely; sensor-based rules can reduce unnecessary watering. This project does not claim measured water savings.

## 3. Cloud concepts mapped to this project

| Concept | Where it appears or how a deployed version uses it |
|---|---|
| Cloud computing | API, storage and dashboard can be hosted independently and reached over the internet. Current run is local. |
| SaaS | A multi-user plant-care dashboard could be offered as a hosted application. |
| PaaS | A managed container platform can run FastAPI and manage health checks. |
| IaaS | A VM and virtual network are alternatives when operations control is required. |
| IoT-to-cloud | Simulator or ESP32 sends JSON over HTTPS. |
| REST and API gateway | `/api/*` endpoints form a stable service interface; a gateway can add quotas and routing. |
| MQTT | Alternative device transport: devices publish to a broker topic and consumers subscribe. It is described, not enabled. |
| Cloud database and time series | SQLite is the local default; set `DATABASE_URL` to use the included PostgreSQL adapter with managed PostgreSQL. The cloud adapter needs provider credentials and a live integration run. |
| Serverless and cloud functions | Ingest/alert processing could move to event-triggered functions. No provider function is deployed. |
| Event-driven design | Each accepted sensor sample triggers storage, alert evaluation and a watering decision. |
| Scalability and elasticity | Stateless API instances can scale behind a load balancer; a queue can absorb bursts. |
| Availability | Health endpoint, backups, multi-zone managed services and recovery procedures are cloud deployment concerns. |
| Authentication and authorization | Human registration/login uses expiring server-side sessions and owner-scoped plant access; device ingestion uses a separate demo API key. The sample key must be replaced for a real deployment. |
| Environment variables and secrets | `DEVICE_API_KEY` and `DATABASE_PATH` are read from environment. Never commit `.env`. |
| Logging and monitoring | Simulator logs readings and request failures. Production should export metrics, traces and alerts. |
| CI/CD | GitHub Actions can run checks and deploy only after secrets, tests and an environment are configured. |

## 4. Stack options

| Option | Components | Difficulty / cost | Expected result |
|---|---|---|---|
| A: laptop only | Python simulator, FastAPI, HTML/JS, SQLite, REST | Beginner; runs locally with no cloud bill | Complete offline demonstration and API docs |
| B: student cloud | Python simulator, FastAPI, hosted dashboard and managed database | Not included in the no-billing project; hosting may require billing | Remote dashboard and managed persistence (future only) |
| C: hardware | ESP32, capacitive probe, DHT22/SHT31, isolated low-voltage pump driver, HTTPS or MQTT | Advanced; hardware and cloud charges may apply | Physical readings and actuator, with local safety cutoff |

The current folder implements Option A. The cloud and hardware material is a plan, not a claim that those services or devices exist.

## 5. Sensor record contract

```json
{
  "device_id": "PLANT-001",
  "soil_moisture": 32,
  "temperature": 29.4,
  "humidity": 61,
  "light_level": 72,
  "water_tank_level": 80,
  "timestamp": "2026-09-29T10:00:00Z"
}
```

Moisture, humidity, light and tank level are percentages; temperature is Celsius; timestamp is UTC ISO-8601. Light is optional and defaults to 50. Tank level is optional; when supplied at 10% or below, the app raises a warning and blocks both automatic and manual watering.

## 6. Simulator behavior

The Python virtual device uses bounded, slowly changing measurements rather than independent white noise. Soil dries each cycle; temperature and humidity drift; light follows a smooth simulated day pattern. Readings are sent every five seconds by default. If the API is down, the simulator preserves readings in a per-device SQLite queue and retries them on later cycles; successful responses remove queued rows. `--offline` generates logs without posting or queueing.

The simulator observes new manual or automatic watering records and raises moisture for a subsequent sample. This represents a virtual plant response; it is not a pump command for hardware.

## 7. Database design and relationships

The local SQLite tables include accounts, hashed session tokens, devices, readings, watering events and alerts. Devices belong to an account; dashboard requests verify that ownership before returning or changing plant data. Set `DATABASE_URL` and install `psycopg[binary]` to use the PostgreSQL adapter. `cloud_schema.sql` documents the matching hosted schema. The adapter and schema have not been validated against a live provider database. A real deployment also needs rate limiting, per-device credentials, backups, monitoring, and a security review.

## 8-9. Watering rules and plant profiles

Water when moisture falls below the device threshold and the two-minute automatic cooldown has passed. The virtual pulse duration is bounded; the demo models a moisture increase and logs the action. Manual duration is limited to 1–10 seconds. The dashboard lets the user set the threshold, toggle automatic decisions, and save a daily schedule using the computer’s local time. A schedule is evaluated when a sensor reading arrives during that minute; it runs no more than once per day and obeys the cooldown and tank-safety checks.

Example starting thresholds in `automation/plant_profiles.py`: succulent 20%, tomato 40%, herb 35%, indoor plant 30%. Actual needs depend on soil, pot, climate and sensor calibration; users should tune these values rather than treat them as horticultural advice.

## 10. API guide

| Method and path | Input / behavior | Key response and errors |
|---|---|---|
| GET `/api/health` | Service status | 200 |
| GET `/api/devices` | List devices and online state | 200 |
| POST `/api/devices` | Device config | 201; 409 duplicate; 422 invalid |
| GET `/api/devices/{id}` | Config, heartbeat, virtual pump status | 200; 404 missing |
| POST `/api/sensors/data` | Validated sample; requires `x-api-key`; duplicate device/timestamp is ignored | 201 new reading; 200 duplicate; 401 bad key; 404 unknown device; 422 invalid |
| GET `/api/devices/{id}/device-state` | Device-key-only read of latest sample and watering actions after `after_id`; only actions from the last five minutes are returned | 200; 401 bad key; 404 unknown device |
| GET `/api/devices/{id}/latest` | Most recent sample | 200; null reading if none |
| GET `/api/devices/{id}/history?limit=100` | Up to 500 samples | 200 |
| PUT `/api/devices/{id}/threshold` | `{ "moisture_threshold": 30 }` | 200; 404; 422 |
| PUT `/api/devices/{id}/schedule` | `{ "enabled": true, "time": "08:00" }` in local 24-hour time | 200; 404; 422 |
| PUT `/api/devices/{id}/auto-water?enabled=false` | Toggle automatic decision | 200; 404 |
| POST `/api/devices/{id}/water` | `{ "duration_seconds": 3 }` | 201; 404; 422 |
| GET `/api/devices/{id}/watering-history` | Latest 100 events | 200 |
| GET `/api/alerts?status=open` | Alerts, optionally filtered | 200 |
| PUT `/api/alerts/{id}/acknowledge` | Acknowledge open alert | 200; 404 |

Account routes are `/api/auth/register`, `/api/auth/login`, `/api/auth/me`, and `/api/auth/logout`. Plant dashboard routes require the signed-in session and are scoped by account ownership. Sensor ingestion remains separately protected by the configured device API key. Before a public release, add rate limits and per-device credentials and review CSRF, proxy, cookie, and database settings for the selected host.

## 11-13. Dashboard, alerts and heartbeat

The browser shows latest moisture, temperature, humidity, light, tank level, device state, virtual pump pulse, history plot, watering history and alerts. It refreshes every five seconds. Low moisture, low tank level (10% or below), and high temperature produce alerts. Low tank level blocks both manual and automatic watering until a later reading reports a safe level. A device that was previously seen but has not reported for 90 seconds produces one offline alert; a later heartbeat resolves it. An alert can be acknowledged. The dashboard can show opt-in browser desktop notifications while it remains open; browser permission is requested only after the user clicks the button. FCM/email/SMS and background push are not connected. Analytics also shows a conservative linear estimate from recent soil readings when enough consistent history exists; it never triggers watering and is not a trained ML model.

## 14. Cloud deployment plans

**No-billing project:** run the app locally using SQLite as described in `docs/deployment.md`. Do not enable cloud billing or Firebase Blaze. Public hosting and managed databases are future work and are not required for the local demonstration.

**AWS-style architecture:** IoT Core or API Gateway -> Lambda/containers -> DynamoDB or Timestream -> SNS; frontend assets in S3/CloudFront; logs/metrics in CloudWatch. Azure: IoT Hub, Functions, Cosmos DB, Notification Hubs and Azure Monitor. GCP: Cloud Run, Firestore/Bigtable, Pub/Sub and Cloud Monitoring. These are equivalent design mappings only.

## 15. Repository layout

`backend/` owns the API and persistence; `automation/` owns decisions and defaults; `sensor_simulator/` represents the device; `frontend/` is the operator dashboard; `hardware/` contains an optional ESP32 adapter; `tests/` contains automated checks; `docs/` holds design and deployment material; `reports/` holds the course report; `screenshots/` is for genuine captures; `sample_data/` is for synthetic examples. The first version keeps route definitions together in `backend/app.py`; splitting them into route/service modules is a maintainability improvement for the next iteration.

## 17. Reproducible local demo

1. Create and activate a Python virtual environment.
2. Install `requirements.txt`.
3. Start `python -m uvicorn backend.app:app --reload`.
4. Open `http://127.0.0.1:8000`.
5. Start `python sensor_simulator/simulator.py --interval 5` in a second terminal.
6. Watch moisture drift, alert creation, virtual pump pulse, and moisture recovery. Manual water and threshold controls are available in the dashboard.
7. Stop either process with Ctrl+C. The SQLite history remains on disk locally.

## 18. Hardware migration

The reference sketch reads an ESP32, capacitive soil sensor and DHT22 over HTTPS, reads an optional fail-safe GPIO 27 float switch, and polls the device-key endpoint for recent watering actions, including dashboard manual requests. The normally-closed switch reports safe only when closed to ground; an open switch/wire reports empty and blocks pump pulses. It persists the action cursor across restarts, skips old events on first boot, and caps each pulse at three seconds with a local cooldown. Calibrate ADC dry/wet readings and use a separate suitable low-voltage supply with a rated relay/MOSFET driver. Never drive a pump directly from GPIO. Add a physical emergency stop, tank-empty cutoff and watchdog before use. The sketch is reference firmware only; it has not been compiled or tested on hardware. Mains wiring is out of scope.

## 19-24. Security, scale, analytics and failures

The demo validates numeric ranges and uses a device key. A deployed system needs per-device identity/rotation, HTTPS, end-user login, server-side ownership checks, least-privilege database roles, secret-manager storage, rate limiting, audit logs and encrypted managed storage. Do not publicly expose actuation routes.

At 10 plants a single managed API and database is sufficient. At 1,000, add a queue, connection pooling, metrics and indexed managed storage. At 100,000, partition/stream ingestion, autoscale stateless workers, use retention/aggregation and regional planning. One million readings is a data volume, not a device count; estimate bytes and write rate from interval and retention before selecting a database. Cache current device state, keep historical data in query-optimized storage, and use backpressure/retries for bursts.

The API includes sample count, average/minimum/maximum moisture and average temperature. A local linear trend estimate is provided when history supports one; the optional trained ML model is not implemented. Failure handling should cover retry with bounded backoff, duplicate/idempotency keys, dead-letter queues, database outages, stale device data, safe default actuator-off, backups and recovery drills. The simulator now stores unsent readings in a durable local SQLite spool and retries on later cycles. `scripts/backup_sqlite.py` and `scripts/restore_sqlite.py` create and verify local SQLite backups/restores. Managed cloud queues, PostgreSQL backup tooling, and recovery drills remain deployment work.

## 25-28. GitHub and proof checklist

Keep `.env`, API secrets, database files and personal sensor data out of Git. Use clear commit messages, an architecture diagram, reproducible commands, licensed assets and a README that separates implemented, simulated and planned features. Only add screenshots captured from a real run; do not fabricate deployment screens, test output or pump behavior. Suggested captures: folder tree, API docs, live readings, history graph, low-moisture alert, automatic/manual event, threshold control, device-offline alert and actual test output. Cloud dashboard and live URL are future proof items until deployed.

## 29-31. Report, resume and interview

Use `../reports/project-report.md` as the report starter and add measured results after testing. Resume wording should say “built a hardware-free IoT simulation with FastAPI, SQLite, threshold automation and dashboard” and must not imply cloud hosting or physical pumping unless those have been completed. Interview prompts and sample answers are in `interview_prep.md`.

