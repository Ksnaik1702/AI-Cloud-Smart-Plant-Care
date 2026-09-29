-- PostgreSQL schema reference. Runtime table names match backend/app.py.
-- The local demo uses SQLite; the API creates equivalent PostgreSQL tables
-- automatically when DATABASE_URL is configured.
CREATE TABLE users (
  user_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT now()::text
);
CREATE TABLE sessions (
  token_hash TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE devices (
  device_id TEXT PRIMARY KEY,
  user_id TEXT REFERENCES users(user_id) ON DELETE CASCADE,
  plant_name TEXT NOT NULL,
  plant_type TEXT NOT NULL,
  location TEXT NOT NULL,
  moisture_threshold DOUBLE PRECISION NOT NULL DEFAULT 30 CHECK (moisture_threshold BETWEEN 5 AND 90),
  auto_water INTEGER NOT NULL DEFAULT 1,
  last_seen TEXT,
  last_watered_at TEXT,
  pump_until TEXT,
  schedule_enabled INTEGER NOT NULL DEFAULT 0,
  schedule_time TEXT,
  last_schedule_date TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE readings (
  id BIGSERIAL PRIMARY KEY,
  device_id TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
  soil_moisture DOUBLE PRECISION NOT NULL CHECK (soil_moisture BETWEEN 0 AND 100),
  temperature DOUBLE PRECISION NOT NULL CHECK (temperature BETWEEN -10 AND 60),
  humidity DOUBLE PRECISION NOT NULL CHECK (humidity BETWEEN 0 AND 100),
  light_level DOUBLE PRECISION CHECK (light_level BETWEEN 0 AND 100),
  timestamp TEXT NOT NULL,
  water_tank_level DOUBLE PRECISION CHECK (water_tank_level BETWEEN 0 AND 100)
);
CREATE INDEX idx_readings_device_time ON readings(device_id,timestamp DESC);
CREATE INDEX idx_watering_events_device_time ON watering_events(device_id,timestamp DESC);
CREATE TABLE watering_events (
  id BIGSERIAL PRIMARY KEY,
  device_id TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
  trigger_type TEXT NOT NULL CHECK (trigger_type IN ('manual','automatic','scheduled')),
  moisture_before DOUBLE PRECISION,
  duration_seconds INTEGER NOT NULL CHECK (duration_seconds BETWEEN 1 AND 10),
  timestamp TEXT NOT NULL
);
CREATE INDEX idx_watering_events_device_time ON watering_events(device_id,timestamp DESC);
CREATE TABLE alerts (
  id BIGSERIAL PRIMARY KEY,
  device_id TEXT NOT NULL REFERENCES devices(device_id) ON DELETE CASCADE,
  alert_type TEXT NOT NULL,
  level TEXT NOT NULL CHECK(level IN ('info','warning','critical')),
  message TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','acknowledged','resolved')),
  created_at TEXT NOT NULL
);
