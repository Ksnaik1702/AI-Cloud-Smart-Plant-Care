from automation.watering_engine import should_water

def test_dry_plant_and_elapsed_cooldown_starts_watering():
    assert should_water(20, 30, True)

def test_moist_plant_does_not_water():
    assert not should_water(35, 30, True)

def test_cooldown_prevents_repeated_watering():
    assert not should_water(20, 30, False)