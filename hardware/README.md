# Optional ESP32 adapter

`ESP32_WiFi_Sensor.ino` sends the same snake_case JSON fields used by the Python simulator, then polls the device-key `/api/devices/{id}/device-state` endpoint for recent automatic or manual watering actions. It retains the action cursor in ESP32 Preferences, ignores old event history on first boot, turns the output off after at most three seconds, and enforces a local two-minute cooldown. An optional normally-closed float switch on GPIO 27 (closed to GND while water is present) reports tank safe/empty and physically blocks a pump pulse when open. The API only returns action events from the preceding five minutes.

## Before using any hardware

1. Install the ESP32 Arduino board package plus DHT sensor library and ArduinoJson.
2. Copy `secrets.example.h` to `secrets.h`; add `hardware/secrets.h` to your ignored local files. Use a unique device key and a valid trusted server root CA certificate. The placeholder certificate does not validate a server.
3. Calibrate dry/wet ADC values for the exact soil probe and board.
4. Confirm the relay's active level without a pump attached; the sketch assumes active-HIGH.
5. Use a separately powered, isolated low-voltage pump circuit with a rated relay/MOSFET. Never connect a pump to an ESP32 GPIO or mains wiring.
6. Add a physical emergency stop, reservoir-empty cutoff and independent hardware maximum-on-time before operating a pump.

For the optional GPIO 27 tank input, use a normally-closed, low-voltage float switch wired between GPIO 27 and GND. The internal pull-up makes an open wire or empty-tank switch read unsafe (0%); only a closed-to-ground switch reports 100%. Verify the exact switch behavior with a meter before connecting any pump.

This is optional reference firmware and has not been compiled or tested on physical hardware. On its first boot it skips existing watering history to prevent old demo events from activating a real pump. It can then receive recent dashboard watering requests while online. Commands created while the board is offline expire after five minutes. Its local pulse and cooldown checks are extra safeguards; add a physical emergency stop and independent tank cutoff before connecting a pump.
