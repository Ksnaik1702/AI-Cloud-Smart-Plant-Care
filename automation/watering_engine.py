def should_water(soil_moisture: float, threshold: float, cooldown_complete: bool) -> bool:
    """Start a bounded virtual watering event only when soil is dry and cooldown passed."""
    return 0 <= soil_moisture < threshold and cooldown_complete