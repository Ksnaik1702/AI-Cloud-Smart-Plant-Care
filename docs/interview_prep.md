# Resume and interview preparation

## Accurate resume wording

**Built a hardware-free IoT plant-care demo using FastAPI, SQLite, and a Python sensor simulator; implemented validated REST ingestion, historical readings, threshold-based virtual watering, alerts, device heartbeat monitoring, and a live dashboard.**

Add “deployed to [provider]” only after an actual deployment. Add ESP32/pump only after physical hardware is built and tested.

## Interview questions and sample answers

### Explain the project

It simulates an IoT plant sensor that sends soil moisture, temperature, humidity and light readings to a REST API. FastAPI validates and stores the readings in SQLite, then checks the plant's moisture threshold. The dashboard shows current state and history, while low moisture and high temperature create alerts. A virtual watering event feeds back into the simulator so I can demonstrate the complete workflow without hardware.

### Why use cloud architecture?

A hosted service can collect readings centrally and let users monitor plants remotely. Managed storage, identity, event processing and monitoring make it possible to grow beyond one laptop. The checked-in version is local and demonstrates those boundaries before connecting a provider.

### How does the watering decision work?

Each device has a configurable moisture threshold. On each validated reading, the backend compares moisture with that threshold and checks whether automatic watering is enabled and the two-minute cooldown has elapsed. It records a bounded virtual event. Physical control would need independent local safety cutoffs.

### What does MQTT add?

MQTT is a lightweight publish/subscribe option. A device publishes measurements to a broker topic and backend consumers subscribe. This decouples devices from individual API consumers and can suit constrained devices, though this MVP uses HTTP REST.

### How are devices authenticated?

The local ingestion route checks an API key in a request header. The sample key is public and only for a local demo. Production should use unique rotated device credentials, HTTPS, secret management, rate limiting and server-side ownership checks for people.

### What is not production-ready?

The app has no end-user login, shared managed database, real pump, cloud notifications or public deployment. SQLite is local single-instance storage. Those items are documented as next steps rather than represented as completed work.

### How would it scale to many plants?

Keep API workers stateless, place an API gateway and queue in front of processing, store time-series data in a managed system indexed by device and time, and autoscale workers. Add retention/aggregation, metrics, backpressure and per-device rate controls.

### How was it tested?

Describe only tests actually run. The test plan covers valid and invalid ingestion, storage, history, threshold decisions, cooldown, alerts, offline detection, manual watering, multiple devices, and failure cases. Record observed output in `docs/test_plan.md` after running the suite.

### What would you improve next?

Add automated API tests, human login with device ownership, a managed database, queued ingestion, CI/CD, actual deployment, then optional ESP32 integration with a fail-safe local actuator controller.
