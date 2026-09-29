"""Synthetic virtual plant. Soil dries gradually and rises after watering actions."""
import argparse
import logging
import math
import random
import time
from datetime import datetime, timezone

import requests
from config import API_URL, DEVICE_ID, API_KEY, INTERVAL_SECONDS, OFFLINE_MODE
from offline_queue import OfflineReadingQueue

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=INTERVAL_SECONDS)
    parser.add_argument("--device-id", default=DEVICE_ID, help="Registered device ID to simulate")
    parser.add_argument("--offline", action="store_true", default=OFFLINE_MODE)
    parser.add_argument("--queue-flush-limit", type=int, default=20)
    args = parser.parse_args()
    if args.interval < 1 or args.queue_flush_limit < 1:
        parser.error("--interval and --queue-flush-limit must be positive")

    soil, temp, humidity, tank = 58.0, 24.0, 55.0, 100.0
    step = 0
    last_action_id = 0
    api_base = API_URL.rsplit("/api/sensors/data", 1)[0]
    device_url = f"{api_base}/api/devices/{args.device_id}/device-state"
    device_headers = {"x-api-key": API_KEY}
    queue = OfflineReadingQueue(args.device_id) if not args.offline else None
    session = requests.Session()

    if not args.offline:
        try:
            response = requests.get(device_url, headers=device_headers, timeout=3)
            response.raise_for_status()
            state = response.json()
            latest = state.get("reading")
            if latest:
                soil = latest["soil_moisture"]
                temp = latest["temperature"]
                humidity = latest["humidity"]
                tank = latest.get("water_tank_level") if latest.get("water_tank_level") is not None else 100.0
            last_action_id = int(state.get("latest_action_id", 0))
        except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
            logging.warning("Could not load device state; starting fresh: %s", exc)

    while True:
        step += 1
        if not args.offline:
            try:
                response = requests.get(
                    device_url,
                    params={"after_id": last_action_id},
                    headers=device_headers,
                    timeout=3,
                )
                response.raise_for_status()
                state = response.json()
                actions = state.get("watering_actions", [])
                if not isinstance(actions, list):
                    raise ValueError("Device state did not contain a watering action list")
                new_actions = [item for item in actions if int(item["id"]) > last_action_id]
                if new_actions:
                    soil = min(95, soil + 18 * len(new_actions))
                    tank = max(0, tank - 5 * len(new_actions))
                    logging.info("Virtual watering action observed; moisture increased")
                last_action_id = max(last_action_id, int(state.get("latest_action_id", last_action_id)))
            except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
                logging.warning("Could not check watering actions (%s); retrying next interval", exc)

        soil = max(5, min(95, soil - random.uniform(0.8, 2.0)))
        temp = max(17, min(38, temp + random.uniform(-0.5, 0.5)))
        humidity = max(30, min(85, humidity + random.uniform(-1.5, 1.5)))
        light = max(5, min(100, 50 + 40 * math.sin(step / 30) + random.uniform(-4, 4)))
        data = {
            "device_id": args.device_id,
            "soil_moisture": round(soil, 1),
            "temperature": round(temp, 1),
            "humidity": round(humidity, 1),
            "light_level": round(light, 1),
            "water_tank_level": round(tank, 1),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logging.info("reading %s", data)
        if not args.offline:
            queue.enqueue(data)
            sent = queue.flush(session, API_URL, device_headers, args.queue_flush_limit)
            if sent:
                logging.info("Uploaded %d queued reading(s); %d remain", sent, queue.pending_count())
        time.sleep(max(1, args.interval))


if __name__ == "__main__":
    main()
