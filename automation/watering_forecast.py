"""Conservative, local-only estimate from a plant's recent soil trend."""

from datetime import datetime, timedelta, timezone
import math


def estimate_watering(readings, threshold, last_seen):
    """Estimate hours to threshold only when recent history supports a trend.

    This is a small linear-regression estimate, not a trained ML model. It never
    starts watering; the configured threshold and safety rules remain in charge.
    """
    now = datetime.now(timezone.utc)
    if not readings:
        return {"status": "collecting", "estimated_hours": None, "samples": 0}
    if not last_seen:
        return {"status": "offline", "estimated_hours": None, "samples": 0}
    seen_at = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
    if seen_at.tzinfo is None:
        seen_at = seen_at.replace(tzinfo=timezone.utc)
    if now - seen_at > timedelta(seconds=90):
        return {"status": "offline", "estimated_hours": None, "samples": 0}
    points = []
    for reading in readings:
        try:
            at = datetime.fromisoformat(str(reading["timestamp"]).replace("Z", "+00:00"))
            if at.tzinfo is None:
                at = at.replace(tzinfo=timezone.utc)
            value = float(reading["soil_moisture"])
            if math.isfinite(value):
                points.append((at, value))
        except (KeyError, TypeError, ValueError):
            continue
    points.sort(key=lambda point: point[0])
    if not points:
        return {"status": "collecting", "estimated_hours": None, "samples": 0}

    current = points[-1][1]
    if current <= float(threshold):
        return {"status": "threshold_reached", "estimated_hours": 0, "samples": len(points)}
    if len(points) < 6 or (points[-1][0] - points[0][0]).total_seconds() < 600:
        return {"status": "collecting", "estimated_hours": None, "samples": len(points)}

    origin = points[0][0]
    xs = [(at - origin).total_seconds() / 3600 for at, _ in points]
    ys = [value for _, value in points]
    mean_x, mean_y = sum(xs) / len(xs), sum(ys) / len(ys)
    variance_x = sum((x - mean_x) ** 2 for x in xs)
    if variance_x == 0:
        return {"status": "stable", "estimated_hours": None, "samples": len(points)}
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / variance_x
    residuals = [y - (mean_y + slope * (x - mean_x)) for x, y in zip(xs, ys)]
    total_variation = sum((y - mean_y) ** 2 for y in ys)
    r_squared = 1 - sum(error * error for error in residuals) / total_variation if total_variation else 0

    if slope >= -0.02:
        return {"status": "stable", "estimated_hours": None, "samples": len(points)}
    if r_squared < 0.55:
        return {"status": "uncertain", "estimated_hours": None, "samples": len(points)}
    hours = (current - float(threshold)) / -slope
    if not math.isfinite(hours) or hours > 168:
        return {"status": "beyond_window", "estimated_hours": None, "samples": len(points)}
    return {"status": "estimated", "estimated_hours": round(max(0, hours), 1), "samples": len(points)}
