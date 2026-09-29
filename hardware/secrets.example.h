# Copy this to hardware/secrets.h and fill values locally. Never commit secrets.h.
# API_URL is the HTTPS base URL followed by /api/sensors/data.
const char *WIFI_SSID = "replace-me";
const char *WIFI_PASSWORD = "replace-me";
const char *DEVICE_ID = "PLANT-001";
const char *DEVICE_API_KEY = "replace-with-a-unique-device-secret";
const char *INGEST_URL = "https://your-service.example/api/sensors/data";
const char *DEVICE_STATE_URL = "https://your-service.example/api/devices/PLANT-001/device-state";
const char *SERVER_ROOT_CA = R"CERT(
-----BEGIN CERTIFICATE-----
REPLACE_WITH_THE_SERVICE_CA_CERTIFICATE
-----END CERTIFICATE-----
)CERT";
