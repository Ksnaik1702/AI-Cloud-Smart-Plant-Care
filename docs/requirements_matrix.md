# Project brief coverage matrix

The brief includes architecture and portfolio goals, not just a code checklist. This matrix distinguishes implemented behavior from design guidance and external work.

| Brief sections | Coverage in project folder | Status |
|---|---|---|
| 1. Explanation and workflow | `docs/system_design.md` | Covered |
| 2. Industry relevance and benefits | `docs/system_design.md` | Covered with qualitative claims only |
| 3. Cloud concepts mapping | `docs/system_design.md` | Covered; production services are explanatory |
| 4. Three technology options | `docs/system_design.md` | Covered |
| 5. Sensor data model | API model + `docs/system_design.md` | Covered; optional water-tank level is ingested and validated |
| 6. Simulator | `sensor_simulator/` | Implemented for synthetic measurements, logging, and durable SQLite spooling/retry while the API is unavailable |
| 7. Cloud data design | SQLite plus PostgreSQL adapter via `DATABASE_URL`; `cloud_schema.sql` | Local SQLite works; PostgreSQL adapter and account/ownership schema are ready for configuration but require provider credentials and live verification |
| 8. Watering rules and cooldown | `automation/`, backend | Threshold, cooldown and scheduled watering implemented as virtual events; schedule runs on the first sensor reading during the selected minute |
| 9. Plant profiles | `automation/plant_profiles.py`, profile API | Profile dropdown, add-plant form, default thresholds, and per-plant custom threshold implemented |
| 10. REST API | `backend/app.py` | Device-key ingestion, account registration/login/logout, session cookies, and owner-protected plant routes implemented |
| 11. Dashboard | `frontend/` | Implemented; browser polling, multi-plant registration/selection, profile controls, custom thresholds, one shared sensor timeline with three spaced and labeled trend lines, and a seven-day watering chart |
| 12. Alerts | Backend and dashboard | Low moisture/low tank/high temperature and acknowledge implemented; optional opt-in browser notifications while the dashboard is open; no FCM/email/SMS |
| 13. Offline detection | Backend device status and alerts | Implemented for devices that were previously seen; 90-second timeout |
| 14. Architecture | `docs/system_design.md`, `docs/architecture.md` | Covered |
| 15. Folder structure | Project folders | Covered with compact single-module backend; route/service split is future cleanup |
| 16. Complete source code | Project files | Local MVP, PostgreSQL adapter and optional ESP32 reference sketch included; provider-specific services remain to configure |
| 17. Virtual simulation | README and guide | Runnable locally; scenario is virtual |
| 18. Hardware version | `hardware/ESP32_WiFi_Sensor.ino`, `hardware/README.md` | Optional ESP32 reference reads sensors, polls recent watering actions, supports a fail-safe GPIO 27 tank float switch and limits pump pulses locally; not hardware-tested |
| 19. Cloud deployment | Dockerfile, Compose, `docs/deployment.md` | Local path ready; hosted Firebase/cloud deployment is not configured or published; Cloud Functions-based ingestion/automation and managed backend hosting are excluded to preserve the no-billing requirement |
| 20. Testing | `tests/`, `docs/test_plan.md`, CI workflow | 31 automated tests pass locally, including durable queue retry and SQLite backup/restore checks. Simulator-to-watering feedback, dashboard visual behavior, browser end-to-end, physical hardware and live-cloud checks remain pending |
| 21. Security | `docs/system_design.md` | Password hashing, expiring hashed session tokens, HttpOnly/SameSite cookies, and per-user device authorization implemented; production rate limits, CSRF review, per-device keys, and provider hardening remain |
| 22. Scalability | `docs/system_design.md` | 10/1,000/100,000 device discussion included |
| 23. Analytics | `/api/devices/{id}/analytics`, `automation/watering_forecast.py` | Average/min/max soil, average climate, watering frequency, plant/device state and a conservative local linear trend estimate; optional trained ML model is not included |
| 24. Failure handling | README and design guide | Duplicate detection, durable simulator SQLite spool, safe database errors, plus local SQLite backup/restore scripts implemented. Cloud-managed queues and backup/recovery drills remain deployment work |
| 25. GitHub upload | README and design guide | Workflow and secret hygiene covered; repository not published |
| 26. README | `README.md` | Written for the runnable local MVP |
| 27-28. Proof strategy/screenshots | design guide and `screenshots/` | Checklist provided; screenshots must be captured from real execution |
| 29. Project report | `reports/project-report.md` | Starter report included |
| 30. Resume/LinkedIn | `docs/interview_prep.md` | Accurate wording included |
| 31. Interview preparation | `docs/interview_prep.md` | Questions and sample answers included |
| Later collection steps | design guide and hardware/cloud docs | PostgreSQL mode, local trend estimation and ESP32 action polling are included; Firebase and the optional trained AI model are not deployed |

## Remaining external work

The folder cannot truthfully show a live cloud database, public deployment, FCM/email/SMS delivery, GitHub history or a working physical pump without a provider account, credentials, a publish action, or hardware. Browser desktop alerts are local and only appear while the dashboard is open; optional ESP32 tank-switch code is reference firmware. Human login and per-user authorization are implemented locally. PostgreSQL connection support is present but needs a managed database to validate. A trained ML predictor and genuine screenshots remain incomplete; the trend forecast is a local heuristic. Schedules are local-time daily triggers and require a device reading during the scheduled minute. No cloud resource was created and no billing was enabled. Cloud provider pricing and quotas change over time and must be checked before any hosting choice.

