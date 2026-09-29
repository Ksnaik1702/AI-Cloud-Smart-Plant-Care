"""Black-box API tests using the standard-library HTTP client."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from http.cookies import SimpleCookie
from uuid import uuid4

import pytest

TEST_COOKIE = None
OWNER_EMAIL = None

def call(base, path, method="GET", payload=None, key="test-device-key", auth=True):
    global TEST_COOKIE
    data=None if payload is None else json.dumps(payload).encode()
    headers={"Accept":"application/json"}
    if data is not None: headers["Content-Type"]="application/json"
    if key is not None: headers["x-api-key"]=key
    if auth and TEST_COOKIE: headers["Cookie"]=f"plant_session={TEST_COOKIE}"
    req=Request(base+path,data=data,headers=headers,method=method)
    try:
        with urlopen(req,timeout=5) as response:
            cookie=SimpleCookie(); cookie.load(response.headers.get("Set-Cookie", ""))
            if "plant_session" in cookie: TEST_COOKIE=cookie["plant_session"].value
            body=response.read()
            if not body: parsed=None
            else:
                try: parsed=json.loads(body)
                except json.JSONDecodeError: parsed=body.decode(errors="replace")
            return response.status,parsed
    except HTTPError as error:
        cookie=SimpleCookie(); cookie.load(error.headers.get("Set-Cookie", ""))
        if "plant_session" in cookie: TEST_COOKIE=cookie["plant_session"].value
        body=error.read()
        try: parsed=json.loads(body)
        except json.JSONDecodeError: parsed=body.decode(errors="replace")
        return error.code,parsed


@pytest.fixture(scope="session")
def server():
    root=Path(__file__).resolve().parents[1]
    db=root/"tests"/".test_run.sqlite3"
    with socket.socket() as probe:
        probe.bind(("127.0.0.1",0)); port=probe.getsockname()[1]
    env=os.environ.copy(); env["DATABASE_PATH"]=str(db); env["DATABASE_URL"]=""; env["DEVICE_API_KEY"]="test-device-key"
    process=subprocess.Popen([sys.executable,"-m","uvicorn","backend.app:app","--host","127.0.0.1","--port",str(port)],cwd=root,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    base=f"http://127.0.0.1:{port}"
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        if process.poll() is not None: pytest.fail("Test API server stopped during startup")
        try:
            status,_=call(base,"/api/health",key=None)
            if status==200: break
        except (URLError,TimeoutError): time.sleep(.2)
    else:
        process.terminate(); pytest.fail("Test API server did not become ready")
    global TEST_COOKIE, OWNER_EMAIL
    TEST_COOKIE=None
    OWNER_EMAIL=f"owner-{uuid4().hex[:12]}@example.com"
    status,_=call(base,"/api/auth/register","POST",{"name":"Test Owner","email":OWNER_EMAIL,"password":"correct-horse-battery"},key=None,auth=False)
    assert status==201
    assert call(base,"/api/devices",key=None,auth=False)[0]==401
    yield base,db
    process.terminate()
    try: process.wait(timeout=5)
    except subprocess.TimeoutExpired: process.kill()


@pytest.fixture()
def device(server):
    base,_=server
    device_id="TEST-"+uuid4().hex[:10].upper()
    payload={"device_id":device_id,"plant_name":"Test Plant","plant_type":"tomato","location":"Test bench","moisture_threshold":30}
    status,_=call(base,"/api/devices","POST",payload,key=None)
    assert status==201
    return device_id


def sample(device_id, **changes):
    value={"device_id":device_id,"soil_moisture":45,"temperature":25,"humidity":55,"light_level":60,"water_tank_level":100}
    value.update(changes)
    return value


def test_health_and_dashboard(server):
    base,_=server
    assert call(base,"/api/health",key=None)[0]==200
    assert call(base,"/",key=None)[0]==200


def test_device_state_endpoint_uses_device_key(server,device):
    base,_=server
    assert call(base,f"/api/devices/{device}/device-state",key=None)[0]==401
    state=call(base,f"/api/devices/{device}/device-state")[1]
    assert state["device_id"]==device and state["reading"] is None
    assert state["watering_actions"]==[] and state["latest_action_id"]==0

def test_bad_device_key_is_rejected(server,device):
    base,_=server
    assert call(base,"/api/sensors/data","POST",sample(device),key="wrong")[0]==401


@pytest.mark.parametrize("field,value",[("soil_moisture",140),("temperature",90),("humidity",-1),("light_level",101),("water_tank_level",101)])
def test_invalid_sensor_values_are_rejected(server,device,field,value):
    base,_=server
    assert call(base,"/api/sensors/data","POST",sample(device,**{field:value}))[0]==422


def test_valid_sample_is_saved_and_history_is_ordered(server,device):
    base,_=server
    assert call(base,"/api/sensors/data","POST",sample(device,soil_moisture=55))[0]==201
    latest=call(base,f"/api/devices/{device}/latest",key=None)[1]["reading"]
    history=call(base,f"/api/devices/{device}/history?limit=60",key=None)[1]
    assert latest["soil_moisture"]==55 and latest["water_tank_level"]==100 and len(history)==1
    assert call(base,f"/api/devices/{device}/watering-history",key=None)[1]==[]


def test_duplicate_reading_is_accepted_without_repeating_side_effects(server,device):
    base,_=server
    payload=sample(device,soil_moisture=15,timestamp="2026-01-02T03:04:05Z")
    status,first=call(base,"/api/sensors/data","POST",payload)
    duplicate_status,second=call(base,"/api/sensors/data","POST",payload)
    assert status==201 and first["duplicate"] is False
    assert duplicate_status==200 and second["duplicate"] is True
    assert len(call(base,f"/api/devices/{device}/history",key=None)[1])==1
    assert len(call(base,f"/api/devices/{device}/watering-history",key=None)[1])==1


def test_low_moisture_alert_automatic_event_and_virtual_pump(server,device):
    base,_=server
    result=call(base,"/api/sensors/data","POST",sample(device,soil_moisture=20))[1]
    assert result["watering_event"]["trigger_type"]=="automatic"
    assert call(base,f"/api/devices/{device}",key=None)[1]["pump_status"] is True
    alerts=call(base,"/api/alerts?status=open",key=None)[1]
    assert any(item["alert_type"]=="LOW_MOISTURE" for item in alerts)


def test_tomato_default_matches_profile_and_custom_threshold_is_supported(server):
    base,_=server
    device_id="TEST-"+uuid4().hex[:10].upper()
    status,created=call(base,"/api/devices","POST",{"device_id":device_id,"plant_name":"Tomato"},key=None)
    assert status==201 and created["moisture_threshold"]==40
    herb_id="TEST-"+uuid4().hex[:10].upper()
    _,herb=call(base,"/api/devices","POST",{"device_id":herb_id,"plant_name":"Herb","plant_type":"herb"},key=None)
    assert herb["moisture_threshold"]==35
    status,profile=call(base,f"/api/devices/{device_id}/plant-profile?plant_type=succulent","PUT",key=None)
    assert status==200 and profile["moisture_threshold"]==20
    assert call(base,f"/api/devices/{device_id}/threshold","PUT",{"moisture_threshold":30},key=None)[1]["moisture_threshold"]==30


def test_daily_schedule_queues_once_and_validates_time(server,device):
    from datetime import datetime
    base,_=server
    schedule_time=datetime.now().astimezone().strftime("%H:%M")
    status,result=call(base,f"/api/devices/{device}/schedule","PUT",{"enabled":True,"time":schedule_time},key=None)
    assert status==200 and result["schedule_enabled"] is True
    result=call(base,"/api/sensors/data","POST",sample(device,soil_moisture=50))[1]
    assert result["watering_event"]["trigger_type"]=="scheduled"
    device_status=call(base,f"/api/devices/{device}",key=None)[1]
    assert device_status["schedule_enabled"] is True and device_status["schedule_time"]==schedule_time
    call(base,"/api/sensors/data","POST",sample(device,soil_moisture=50))
    events=call(base,f"/api/devices/{device}/watering-history",key=None)[1]
    assert len(events)==1 and events[0]["trigger_type"]=="scheduled"
    assert call(base,f"/api/devices/{device}/schedule","PUT",{"enabled":True,"time":"24:00"},key=None)[0]==422


def test_low_tank_alert_blocks_automatic_and_manual_watering(server,device):
    base,_=server
    result=call(base,"/api/sensors/data","POST",sample(device,soil_moisture=15,water_tank_level=8))[1]
    assert result["watering_event"] is None
    alerts=call(base,"/api/alerts?status=open",key=None)[1]
    assert any(item["alert_type"]=="LOW_WATER_TANK" for item in alerts)
    assert call(base,f"/api/devices/{device}/water","POST",{"duration_seconds":3},key=None)[0]==409
    events=call(base,f"/api/devices/{device}/watering-history",key=None)[1]
    assert events==[]
    call(base,"/api/sensors/data","POST",sample(device,soil_moisture=15,water_tank_level=50))
    alerts=call(base,"/api/alerts",key=None)[1]
    assert not any(item["alert_type"]=="LOW_WATER_TANK" and item["status"]=="open" for item in alerts)


def test_cooldown_prevents_rapid_automatic_repeat(server,device):
    base,_=server
    call(base,"/api/sensors/data","POST",sample(device,soil_moisture=20))
    result=call(base,"/api/sensors/data","POST",sample(device,soil_moisture=19))[1]
    events=call(base,f"/api/devices/{device}/watering-history",key=None)[1]
    assert result["watering_event"] is None and len(events)==1


def test_manual_water_is_logged_and_duration_is_bounded(server,device):
    base,_=server
    assert call(base,f"/api/devices/{device}/water","POST",{"duration_seconds":3},key=None)[0]==201
    assert call(base,f"/api/devices/{device}/water","POST",{"duration_seconds":3},key=None)[0]==409
    assert call(base,f"/api/devices/{device}",key=None)[1]["pump_status"] is True
    assert call(base,f"/api/devices/{device}/water","POST",{"duration_seconds":99},key=None)[0]==422
    events=call(base,f"/api/devices/{device}/watering-history",key=None)[1]
    assert events[0]["trigger_type"]=="manual"


def test_virtual_pump_turns_off_after_its_pulse(server,device):
    base,db=server
    call(base,f"/api/devices/{device}/water","POST",{"duration_seconds":3},key=None)
    with sqlite3.connect(db) as conn:
        old=(datetime.now(timezone.utc)-timedelta(seconds=5)).isoformat()
        conn.execute("UPDATE devices SET pump_until=? WHERE device_id=?",(old,device))
    assert call(base,f"/api/devices/{device}",key=None)[1]["pump_status"] is False


def test_threshold_profiles_and_auto_toggle(server,device):
    base,_=server
    assert call(base,f"/api/devices/{device}/threshold","PUT",{"moisture_threshold":25},key=None)[1]["moisture_threshold"]==25
    assert call(base,f"/api/devices/{device}/auto-water?enabled=false","PUT",key=None)[1]["auto_water"] is False
    assert "tomato" in call(base,"/api/plant-profiles",key=None)[1]
    assert call(base,f"/api/devices/{device}/plant-profile?plant_type=herb","PUT",key=None)[1]["moisture_threshold"]==35


def test_auto_water_can_be_disabled(server,device):
    base,_=server
    call(base,f"/api/devices/{device}/auto-water?enabled=false","PUT",key=None)
    result=call(base,"/api/sensors/data","POST",sample(device,soil_moisture=10))[1]
    assert result["watering_event"] is None


def test_alert_acknowledgement(server,device):
    base,_=server
    call(base,"/api/sensors/data","POST",sample(device,soil_moisture=20))
    alert=call(base,"/api/alerts?status=open",key=None)[1][0]
    status,result=call(base,f"/api/alerts/{alert['id']}/acknowledge","PUT",key=None)
    assert status==200 and result["status"]=="acknowledged"


def test_high_temperature_alert_resolves(server,device):
    base,_=server
    call(base,"/api/sensors/data","POST",sample(device,temperature=39))
    assert any(a["alert_type"]=="HIGH_TEMPERATURE" for a in call(base,"/api/alerts?status=open",key=None)[1])
    call(base,"/api/sensors/data","POST",sample(device,temperature=25))
    assert not any(a["alert_type"]=="HIGH_TEMPERATURE" and a["status"]=="open" for a in call(base,"/api/alerts",key=None)[1])


def test_offline_alert_and_heartbeat_recovery(server,device):
    base,db=server
    call(base,"/api/sensors/data","POST",sample(device))
    with sqlite3.connect(db) as conn:
        old=(datetime.now(timezone.utc)-timedelta(minutes=3)).isoformat()
        conn.execute("UPDATE devices SET last_seen=? WHERE device_id=?",(old,device))
    assert call(base,f"/api/devices/{device}",key=None)[1]["status"]=="offline"
    assert any(a["alert_type"]=="DEVICE_OFFLINE" for a in call(base,"/api/alerts?status=open",key=None)[1])
    call(base,"/api/sensors/data","POST",sample(device))
    assert call(base,f"/api/devices/{device}",key=None)[1]["status"]=="online"


def test_second_device_data_is_isolated(server,device):
    base,_=server
    other="TEST-"+uuid4().hex[:10].upper()
    assert call(base,"/api/devices","POST",{"device_id":other,"plant_name":"Other","plant_type":"herb","location":"Lab","moisture_threshold":35},key=None)[0]==201
    call(base,"/api/sensors/data","POST",sample(other,soil_moisture=50))
    assert call(base,f"/api/devices/{other}/latest",key=None)[1]["reading"]["soil_moisture"]==50
    assert call(base,f"/api/devices/{device}/latest",key=None)[1]["reading"] is None


def test_analytics_summary(server,device):
    base,_=server
    call(base,"/api/sensors/data","POST",sample(device,soil_moisture=40))
    call(base,"/api/sensors/data","POST",sample(device,soil_moisture=60))
    call(base,f"/api/devices/{device}/water","POST",{"duration_seconds":3},key=None)
    result=call(base,f"/api/devices/{device}/analytics",key=None)[1]
    assert result["samples"]==2 and result["avg_moisture"]==50
    assert result["avg_humidity"]==55 and result["total_watering_events"]==1
    assert result["watering_events_today"]==1 and result["plant_health"]=="Healthy" and result["device_status"]=="online"


def test_0_account_login_ownership_and_logout(server,device):
    base,_=server
    owner_cookie=TEST_COOKIE
    assert call(base,"/api/auth/me",key=None)[0]==200
    status,second=call(base,"/api/auth/register","POST",{"name":"Other Owner","email":f"other-{uuid4().hex[:12]}@example.com","password":"another-secure-passphrase"},key=None,auth=False)
    assert status==201
    assert call(base,"/api/devices",key=None)[1]==[]
    assert call(base,f"/api/devices/{device}",key=None)[0]==404
    call(base,"/api/auth/logout","POST",key=None)
    assert call(base,"/api/auth/me",key=None)[0]==401
    status,_=call(base,"/api/auth/login","POST",{"name":"Test Owner","email":OWNER_EMAIL,"password":"correct-horse-battery"},key=None,auth=False)
    assert status==200
    assert any(d["device_id"]==device for d in call(base,"/api/devices",key=None)[1])





def test_database_failure_returns_service_unavailable(server):
    base,db=server
    with sqlite3.connect(db) as conn: conn.execute("DROP TABLE devices")
    status,result=call(base,"/api/devices",key=None)
    assert status==503 and result["detail"]=="Database is temporarily unavailable"


