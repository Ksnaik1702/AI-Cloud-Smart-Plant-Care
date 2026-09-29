# AI Cloud Smart Plant Care and Watering System

A hardware-free IoT/cloud computing course project. The virtual plant sends synthetic readings to a FastAPI REST service. The backend validates and stores them in SQLite, applies threshold and cooldown rules, records virtual pump events, and serves a dashboard with current measurements, history and alerts.

## Features implemented

- Python sensor simulator with slowly changing soil, temperature, humidity and light data.
- REST API with schema validation, demo device API key, duplicate-reading detection and generated Swagger docs.
- SQLite storage for devices, readings, watering events and alerts.
- Editable moisture threshold, plant profiles, automatic-water toggle, once-daily scheduled watering and manual watering.
- Automatic watering cooldown, bounded virtual pump pulse, daily schedule and simulator moisture response.
- Low-moisture, low-water-tank, high-temperature and previously-seen-device-offline alerts; tank protection pauses watering below 10%; optional browser desktop alerts while the dashboard is open.
- Live dashboard polling, sensor trends, seven-day watering chart, device state, watering history and alert acknowledgement.
- Plant analytics for average/min/max soil, average temperature/humidity, watering counts, plant health and device status.
- A cautious, local linear-trend estimate for time to the configured moisture threshold; it never triggers watering and reports when there is not enough reliable data.
- Optional ESP32 reference firmware polls recent manual and automatic watering actions, supports a fail-safe GPIO 27 tank float switch, and has a persistent action cursor and local pump pulse limit; physical hardware behavior is not verified.
- Durable per-device SQLite queue for simulator readings during API outages; local SQLite backup/restore utilities; aggregated readings endpoint, Dockerfile, local Compose file, report and documentation.

The actuator in the default demo is virtual. Human accounts, session login, and per-account plant ownership work locally. Browser notifications are optional and only work while the dashboard is open. FCM/email/SMS, a managed cloud database, public deployment, and physical actuator are not connected. PostgreSQL support is optional and is not needed to run this project locally. No cloud billing has been enabled.

## Run on Windows

Install Python 3.10 or newer. In VS Code, open a terminal in this folder and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn backend.app:app --reload
```

Open `http://127.0.0.1:8000`, create an account with a password of at least 12 characters, then sign in. In a second terminal, activate the same virtual environment and run:

```powershell
python sensor_simulator\simulator.py --interval 5
```

The dashboard supports multiple registered plants, four built-in plant profiles, and a custom moisture threshold per plant. The tomato profile default is 40%; the threshold stays editable. Add plants in the Plant profiles and setup panel, then run a simulator for each device ID (for example, `python sensor_simulator\simulator.py --device-id PLANT-002 --interval 5`). The simulator starts near 58% moisture and gradually dries the virtual soil. Below the configured threshold, the backend creates an automatic event and the simulator raises its next reading. Use **Water now**, the automatic watering toggle, and the threshold control to explore the system. Stop processes with Ctrl+C.

Generate readings without sending them:

```powershell
python sensor_simulator\simulator.py --offline
```

API docs: `http://127.0.0.1:8000/docs`.

If the API stops temporarily, normal simulator mode keeps unsent readings in an ignored local SQLite queue and retries them when the API is reachable. `--offline` only prints simulated readings and deliberately does not queue them. The dashboard’s **Enable desktop alerts** button requests browser permission only after you click it.

Create a verified local database backup with `python scripts/backup_sqlite.py`. Restore a backup to a new path (the destination must not already exist) with `python scripts/restore_sqlite.py backups\plant_care-YYYYMMDDTHHMMSSZ.sqlite3 restored\plant_care.db`. These tools cover the local SQLite database only; they do not back up a managed PostgreSQL database.

## Run automated tests

```powershell
python -m pytest
```

The automated suite starts an isolated local API process and covers validation, persistence, thresholds, cooldown, manual and automatic virtual actions, alerts, device status, multiple devices and database error responses. See `docs/test_plan.md` for the complete scenario list. Record results only after observing them.

## Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| POST | `/api/auth/register` | Create an account and sign in |
| POST | `/api/auth/login` | Sign in |
| GET | `/api/auth/me` | Current account |
| POST | `/api/auth/logout` | End the current session |
| GET, POST | `/api/devices` | List and register devices |
| GET | `/api/devices/{id}` | Device configuration and status |
| POST | `/api/sensors/data` | Ingest sample; requires `x-api-key` |
| GET | `/api/devices/{id}/device-state` | Device-key endpoint for the latest sample and recent watering actions (five-minute window); requires `x-api-key` |
| GET | `/api/devices/{id}/latest` | Latest sample |
| GET | `/api/devices/{id}/history?limit=100` | Historical sensor data |
| GET | `/api/devices/{id}/analytics` | Count, rolling summary values, and conservative soil trend estimate |
| GET | `/api/plant-profiles` | Default profile thresholds |
| PUT | `/api/devices/{id}/plant-profile?plant_type=herb` | Apply a profile |
| PUT | `/api/devices/{id}/threshold` | Update moisture threshold |
| PUT | `/api/devices/{id}/schedule` | Save or disable daily local-time watering schedule |
| PUT | `/api/devices/{id}/auto-water?enabled=false` | Toggle automatic watering |
| POST | `/api/devices/{id}/water` | Record a bounded manual virtual action |
| GET | `/api/devices/{id}/watering-history` | Watering events |
| GET | `/api/alerts?status=open` | List/filter alerts |
| PUT | `/api/alerts/{id}/acknowledge` | Acknowledge an alert |

Account routes use an HttpOnly session cookie. Plant controls and data require sign-in and are limited to plants owned by that account. The first account created in a fresh local database claims the seeded `PLANT-001` demo plant; later accounts see only their own plants. Sensor ingestion uses the default local key `demo-device-key`; override it with `DEVICE_API_KEY`. This sample key is public and is not suitable for deployment. `ALLOWED_ORIGINS` controls cross-origin development access.

## Docker

```powershell
docker compose up --build
```

Open `http://localhost:8000`. Compose persists the local SQLite demo database in a named volume. For cloud scaling, migrate to a managed shared database first; a container's local SQLite file is not a cloud database.

## Folder guide

- `backend/`: REST API and local persistence.
- `automation/`: plant defaults and watering decision.
- `sensor_simulator/`: virtual IoT device.
- `frontend/`: browser dashboard.
- `hardware/`: optional ESP32 sensor, tank float switch and safe pump pulse reference sketch.
- `scripts/`: local SQLite backup and non-overwriting restore tools.
- `cloud_schema.sql`: PostgreSQL schema reference including user ownership.
- `tests/`: automated API and decision tests.
- `docs/`: architecture, deployment, security, test matrix and requirements coverage.
- `reports/`: course project report starter.
- `sample_data/`: synthetic data example.
- `screenshots/`: capture genuine screenshots after running the demo.

## Next cloud and hardware stages

The local setup remains free and does not need a cloud account. The application is prepared for PostgreSQL through `DATABASE_URL`, but a live cloud database and hosted website are not connected. Hosting providers can require a payment method or charge beyond a changing free quota; no provider was selected and no billing was enabled. See `docs/deployment.md` before choosing a host.

## GitHub proof of work

Keep `.env`, secret keys, `.venv`, logs and `plant_care.db` out of Git. Add only screenshots and deployment links that came from a real run. Use small descriptive commits and label features as implemented, simulated or planned. Do not put credentials in source, issues or screenshots.
