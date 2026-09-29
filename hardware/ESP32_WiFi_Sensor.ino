/*
  Optional adapter for an ESP32, capacitive soil probe, DHT22 and low-voltage pump.
  Libraries: DHT sensor library, ArduinoJson. Copy secrets.example.h to secrets.h
  and supply Wi-Fi credentials, API URL/key, and the server's trusted root CA.
  Relay is assumed active-HIGH; confirm your module before connecting a pump.
*/
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <Preferences.h>
#include "secrets.h"

constexpr int SOIL_PIN = 34;
constexpr int DHT_PIN = 4;
constexpr int PUMP_PIN = 26;
constexpr int LIGHT_PIN = 35;
constexpr int TANK_OK_PIN = 27; // NC float switch to GND when water is present.
constexpr int DHT_TYPE = DHT22;
constexpr int DRY_ADC = 3200;  // Calibrate on your own sensor.
constexpr int WET_ADC = 1200;  // Calibrate on your own sensor.
constexpr uint32_t SAMPLE_EVERY_MS = 60000;
constexpr uint32_t MAX_PUMP_MS = 3000;
constexpr uint32_t PUMP_COOLDOWN_MS = 120000;
constexpr uint32_t ACTION_POLL_EVERY_MS = 2000;

DHT dht(DHT_PIN, DHT_TYPE);
WiFiClientSecure tls;
Preferences preferences;
uint32_t lastSampleAt = 0;
uint32_t lastActionPollAt = 0;
uint32_t pumpStartedAt = 0;
uint32_t lastPumpAt = 0;
uint32_t activePumpMs = 0;
uint64_t lastActionId = 0;
bool pumpOn = false;
bool actionCursorInitialized = false;

float readSoilPercent() {
  int raw = analogRead(SOIL_PIN);
  float value = 100.0f * (DRY_ADC - raw) / float(DRY_ADC - WET_ADC);
  return constrain(value, 0.0f, 100.0f);
}

void stopPump() {
  digitalWrite(PUMP_PIN, LOW);
  pumpOn = false;
  activePumpMs = 0;
}

bool startSafePulse(uint32_t requestedMs, bool tankAllowsWatering) {
  if (!tankAllowsWatering || requestedMs == 0 || pumpOn ||
      digitalRead(TANK_OK_PIN) != LOW ||
      (lastPumpAt != 0 && millis() - lastPumpAt < PUMP_COOLDOWN_MS)) return false;
  digitalWrite(PUMP_PIN, HIGH);
  pumpOn = true;
  pumpStartedAt = millis();
  lastPumpAt = millis();
  activePumpMs = min(requestedMs, MAX_PUMP_MS);
  Serial.printf("Pump pulse started for %lu ms.\n", (unsigned long)activePumpMs);
  return true;
}

void sendReading(float soil, float temperature, float humidity, float light, float tankLevel) {
  if (WiFi.status() != WL_CONNECTED) return;
  HTTPClient http;
  if (!http.begin(tls, INGEST_URL)) return;
  http.addHeader("Content-Type", "application/json");
  http.addHeader("x-api-key", DEVICE_API_KEY);

  JsonDocument payload;
  payload["device_id"] = DEVICE_ID;
  payload["soil_moisture"] = soil;
  payload["temperature"] = temperature;
  payload["humidity"] = humidity;
  payload["light_level"] = light;
  payload["water_tank_level"] = tankLevel;
  String body;
  serializeJson(payload, body);

  int status = http.POST(body);
  if (status < 200 || status >= 300) {
    Serial.printf("Ingest failed: HTTP %d\n", status);
  }
  http.end();
}

void pollWateringActions() {
  if (WiFi.status() != WL_CONNECTED || millis() - lastActionPollAt < ACTION_POLL_EVERY_MS) return;
  lastActionPollAt = millis();
  char url[256];
  snprintf(url, sizeof(url), "%s?after_id=%llu", DEVICE_STATE_URL,
           (unsigned long long)lastActionId);
  HTTPClient http;
  if (!http.begin(tls, url)) return;
  http.addHeader("x-api-key", DEVICE_API_KEY);
  int status = http.GET();
  if (status != 200) {
    Serial.printf("Action poll failed: HTTP %d\n", status);
    http.end();
    return;
  }

  JsonDocument state;
  DeserializationError error = deserializeJson(state, http.getString());
  http.end();
  if (error) {
    Serial.println("Action poll response could not be read.");
    return;
  }

  // On first boot, skip historical water records so old demo events cannot
  // unexpectedly start a real pump. The cursor is retained across restarts.
  if (!actionCursorInitialized) {
    lastActionId = state["latest_action_id"] | (uint64_t)0;
    preferences.putULong64("action_id", lastActionId);
    actionCursorInitialized = true;
    return;
  }

  JsonArray actions = state["watering_actions"].as<JsonArray>();
  for (JsonObject action : actions) {
    uint64_t id = action["id"] | (uint64_t)0;
    if (id <= lastActionId) continue;
    lastActionId = id;
    preferences.putULong64("action_id", lastActionId);

    bool tankAllowsWatering = true;
    JsonVariantConst reading = state["reading"];
    if (!reading.isNull() && !reading["water_tank_level"].isNull())
      tankAllowsWatering = reading["water_tank_level"].as<float>() > 10.0f;
    uint32_t requestedMs = (action["duration_seconds"] | 0) * 1000UL;
    if (!startSafePulse(requestedMs, tankAllowsWatering))
      Serial.println("Water action skipped by the local tank, pulse, or cooldown safety check.");
    break; // Process actions in order, one at a time.
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PUMP_PIN, OUTPUT);
  pinMode(TANK_OK_PIN, INPUT_PULLUP);
  stopPump(); // Fail-safe: actuator is off after reset.
  preferences.begin("plant-care", false);
  lastActionId = preferences.getULong64("action_id", 0);
  actionCursorInitialized = preferences.isKey("action_id");
  analogReadResolution(12);
  dht.begin();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) delay(500);
  tls.setCACert(SERVER_ROOT_CA); // Never disable certificate validation in a deployed device.
}

void loop() {
  if (pumpOn && millis() - pumpStartedAt >= activePumpMs) stopPump();
  pollWateringActions();
  if (millis() - lastSampleAt < SAMPLE_EVERY_MS) { delay(20); return; }
  lastSampleAt = millis();

  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();
  if (isnan(temperature) || isnan(humidity)) {
    Serial.println("DHT read failed; skipping this sample.");
    return;
  }
  float tankLevel = digitalRead(TANK_OK_PIN) == LOW ? 100.0f : 0.0f;
  sendReading(readSoilPercent(), temperature, humidity,
              100.0f * analogRead(LIGHT_PIN) / 4095.0f, tankLevel);
}
