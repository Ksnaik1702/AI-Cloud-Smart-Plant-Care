# Architecture, cloud concepts and extension guide

## Data flow

```text
Synthetic Python sensor (or optional ESP32)
       | HTTPS JSON + device API key
       v
FastAPI REST service -> validation -> watering policy
       |                         |
       v                         v
SQLite / PostgreSQL readings/events       alerts + virtual pump event
       \                         /
             Browser dashboard
```

Each sample includes device ID, soil moisture percent, temperature in Celsius, relative humidity percent, light percent, and a UTC timestamp. The API checks ranges, records history and updates the heartbeat. A low reading creates an alert and, when automatic watering is enabled and cooldown has passed, a bounded virtual watering event. The simulator models moisture rising after that event.

## Cloud concepts shown

- **Cloud computing / SaaS:** plant monitoring can be offered remotely to many users; this MVP runs locally to make the flow reproducible.
- **PaaS / serverless:** deploy FastAPI to a managed app platform, or split ingestion and alert handling into event-triggered functions.
- **REST / API gateway:** `/api/*` is the service boundary; a managed gateway can add rate limits, routing and authentication.
- **Cloud database / time series:** SQLite is the local default; set DATABASE_URL and install requirements-cloud.txt to use the PostgreSQL adapter. Index device and timestamp, retain raw data for a set period, and aggregate older readings.
- **Event-driven architecture:** an accepted sample triggers watering and alert decisions. At larger scale, publish samples to a queue or event stream to keep ingestion responsive.
- **Availability and elasticity:** run stateless API instances behind a load balancer; store shared state in managed services, add health checks and backups.
- **Monitoring:** collect structured logs, error rates, request latency, ingestion counts and offline-device metrics; alert on service failures.
- **CI/CD:** GitHub Actions can run checks and deploy after a reviewed main-branch change.
- **IaaS:** virtual machines and networks are an option, though managed platforms reduce operations work for this project.

## Storage model

- `devices`: plant profile, location, moisture threshold, auto-water setting, last seen and last watered.
- `readings`: append-only time series, indexed by `(device_id, timestamp)`.
- `watering_events`: manual or automatic action, trigger, duration and moisture before action.
- `alerts`: device, alert type, severity, message and lifecycle status.

Devices now store an owner identity, and dashboard reads/writes require a signed-in session and enforce ownership. Do not trust a device ID from a browser as authorization; production also needs per-device credentials.

## Rules and safeguards

Water only below the configured threshold. Require a two-minute cooldown between automatic events, bound duration to 1–10 seconds for this demo, and validate every sensor field. A real pump also needs a hardware fail-safe, non-blocking control, reservoir check, maximum run time and emergency stop. Never actuate mains voltage from student hardware; use suitable isolated low-voltage components and supervision.

## Security

Human accounts use scrypt password hashes and expiring random session tokens whose hashes are stored in the database. Browser sessions use HttpOnly, SameSite cookies; every plant dashboard route verifies ownership. The ingestion route separately requires an `x-api-key` and compares it safely. The local key is intentionally a demo value. Before deployment, inject a random key using a secret manager, rotate to per-device credentials, use HTTPS, rate limit requests, and review CSRF and proxy settings. Encrypt cloud disks and backups, restrict database service accounts, redact secrets from logs, and set retention limits.

The dashboard requires an account locally. Public deployment is still unconfigured; email/SMS/push requires a provider and credentials and is not enabled here. Analytics also shows a conservative linear estimate from recent soil readings when enough consistent history exists; it never triggers watering and is not a trained ML model.

## Student cloud deployment shape

Public hosting and managed databases remain unconfigured because no provider has been selected and the project must stay within the user’s no-payment preference. The project has local account login and PostgreSQL support, but those are not proof of a live cloud service. Do not enable billing or a paid plan for the current demonstration; its provider mappings are for coursework only.

AWS-style mapping: IoT Core/API Gateway -> Lambda or container service -> DynamoDB/Timestream -> SNS; static site in S3/CloudFront and logs/metrics in CloudWatch. Azure equivalents include IoT Hub, Functions, Cosmos DB, Notification Hubs and Azure Monitor. GCP equivalents include HTTPS Load Balancing/Cloud Run, Firestore or Bigtable, Pub/Sub and Cloud Monitoring. These are architecture mappings, not deployed integrations.

## Optional ESP32 path

The reference sketch sends the same JSON from an ESP32 and polls the device-key endpoint for recent automatic or manual watering actions. It persists the action cursor across restarts, skips old events on first boot, uses an optional GPIO 27 fail-safe float switch and reports the tank state, and caps pump pulses at three seconds with a local cooldown. Use a capacitive soil probe and DHT22/SHT31, calibrate dry/wet ADC values, and power any pump with a separate low-voltage supply through a correctly rated relay/MOSFET. Never connect a pump directly to a GPIO. The sketch is reference firmware only; it has not been compiled or tested on hardware.

## Next steps

1. Complete browser end-to-end checks and expand CI coverage.
2. Configure and validate PostgreSQL on a chosen provider.
3. Deploy only after choosing a hosting plan and reviewing cost, security, and secrets.
4. Add a managed queue for ingestion-to-automation decoupling; the simulator already has a local SQLite retry spool.
5. Add retention/aggregation and external notification delivery (FCM/email/SMS); local browser alerts are available only while the dashboard is open.
6. Bench-test ESP32 command polling only after safe hardware design.

For the detailed requirements matrix, cloud deployment guide, hardware sketch notes, complete test plan, and current implementation limits, see [system_design.md](system_design.md), [requirements_matrix.md](requirements_matrix.md), and [deployment.md](deployment.md).
