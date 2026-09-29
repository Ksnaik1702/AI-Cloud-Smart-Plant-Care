from __future__ import annotations
import os, sqlite3, secrets, logging
from datetime import datetime, timezone, timedelta
import hashlib, secrets
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Depends, Query, Cookie, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from automation.watering_engine import should_water
from automation.watering_forecast import estimate_watering

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("DATABASE_PATH", ROOT / "plant_care.db"))
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DEVICE_API_KEY = os.getenv("DEVICE_API_KEY", "demo-device-key")
app = FastAPI(title="Cloud Smart Plant Care API", version="1.0.0", description="A hardware-free IoT cloud computing project demo")
allowed_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(CORSMiddleware,allow_origins=allowed_origins,allow_methods=["GET","POST","PUT"],allow_headers=["Content-Type","x-api-key"])

@app.exception_handler(sqlite3.Error)
async def database_error_handler(request, exc):
    logging.getLogger("plant-care").error("Database request failed (%s)",type(exc).__name__)
    return JSONResponse(status_code=503,content={"detail":"Database is temporarily unavailable"})

try:
    import psycopg
    app.add_exception_handler(psycopg.Error,database_error_handler)
except ImportError:
    pass

class ReadingIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)
    soil_moisture: float = Field(ge=0, le=100)
    temperature: float = Field(ge=-10, le=60)
    humidity: float = Field(ge=0, le=100)
    light_level: float = Field(default=50, ge=0, le=100)
    water_tank_level: Optional[float] = Field(default=None, ge=0, le=100)
    timestamp: Optional[datetime] = None

class AccountIn(BaseModel):
    email: str = Field(min_length=6, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=12, max_length=128)

class RegistrationIn(AccountIn):
    name: str = Field(min_length=1, max_length=80)

class DeviceIn(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)
    plant_name: str = Field(default="Tomato Plant", min_length=1, max_length=80)
    plant_type: str = Field(default="tomato", max_length=40)
    location: str = Field(default="Indoor", max_length=100)
    moisture_threshold: Optional[float] = Field(default=None, ge=5, le=90)

class ThresholdIn(BaseModel):
    moisture_threshold: float = Field(ge=5, le=90)

class WaterIn(BaseModel):
    duration_seconds: int = Field(default=3, ge=1, le=10)

class ScheduleIn(BaseModel):
    enabled: bool
    time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")

def now_iso(): return datetime.now(timezone.utc).isoformat()
class PostgresConnection:
    """Small adapter for the parameter placeholders shared by SQLite/Postgres."""
    def __init__(self, connection): self.connection=connection
    def __enter__(self): self.connection.__enter__(); return self
    def __exit__(self, exc_type, exc, tb): return self.connection.__exit__(exc_type,exc,tb)
    def execute(self, sql, params=()): return self.connection.execute(sql.replace("?", "%s"),params)

def connect():
    if DATABASE_URL:
        import psycopg
        from psycopg.rows import dict_row
        return PostgresConnection(psycopg.connect(DATABASE_URL,row_factory=dict_row))
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(user_id TEXT PRIMARY KEY, name TEXT NOT NULL DEFAULT '', email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, expires_at TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS devices(device_id TEXT PRIMARY KEY, user_id TEXT, plant_name TEXT NOT NULL, plant_type TEXT NOT NULL, location TEXT NOT NULL, moisture_threshold REAL NOT NULL DEFAULT 30, auto_water INTEGER NOT NULL DEFAULT 1, last_seen TEXT, last_watered_at TEXT, pump_until TEXT, schedule_enabled INTEGER NOT NULL DEFAULT 0, schedule_time TEXT, last_schedule_date TEXT, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS readings(id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT NOT NULL REFERENCES devices(device_id), soil_moisture REAL NOT NULL, temperature REAL NOT NULL, humidity REAL NOT NULL, light_level REAL NOT NULL, timestamp TEXT NOT NULL, water_tank_level REAL);
        CREATE INDEX IF NOT EXISTS idx_readings_device_time ON readings(device_id, timestamp DESC);
        CREATE TABLE IF NOT EXISTS watering_events(id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT NOT NULL REFERENCES devices(device_id), trigger_type TEXT NOT NULL, moisture_before REAL, duration_seconds INTEGER NOT NULL, timestamp TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT NOT NULL REFERENCES devices(device_id), alert_type TEXT NOT NULL, level TEXT NOT NULL, message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL);
        """)
        user_columns={r[1] for r in c.execute("PRAGMA table_info(users)")}
        if "name" not in user_columns: c.execute("ALTER TABLE users ADD COLUMN name TEXT NOT NULL DEFAULT ''")
        columns={r[1] for r in c.execute("PRAGMA table_info(devices)")}
        if "user_id" not in columns: c.execute("ALTER TABLE devices ADD COLUMN user_id TEXT")
        if "pump_until" not in columns: c.execute("ALTER TABLE devices ADD COLUMN pump_until TEXT")
        columns={r[1] for r in c.execute("PRAGMA table_info(devices)")}
        if "schedule_enabled" not in columns: c.execute("ALTER TABLE devices ADD COLUMN schedule_enabled INTEGER NOT NULL DEFAULT 0")
        if "schedule_time" not in columns: c.execute("ALTER TABLE devices ADD COLUMN schedule_time TEXT")
        if "last_schedule_date" not in columns: c.execute("ALTER TABLE devices ADD COLUMN last_schedule_date TEXT")
        columns={r[1] for r in c.execute("PRAGMA table_info(readings)")}
        if "water_tank_level" not in columns: c.execute("ALTER TABLE readings ADD COLUMN water_tank_level REAL")
        c.execute("INSERT OR IGNORE INTO devices(device_id,plant_name,plant_type,location,moisture_threshold,created_at) VALUES(?,?,?,?,?,?)", ("PLANT-001","Tomato Plant","tomato","Window sill",40,now_iso()))

def init_postgres():
    statements=[
        "CREATE TABLE IF NOT EXISTS users(user_id TEXT PRIMARY KEY,name TEXT NOT NULL DEFAULT '',email TEXT NOT NULL UNIQUE,password_hash TEXT NOT NULL,created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,expires_at TEXT NOT NULL,created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS devices(device_id TEXT PRIMARY KEY,user_id TEXT REFERENCES users(user_id),plant_name TEXT NOT NULL,plant_type TEXT NOT NULL,location TEXT NOT NULL,moisture_threshold DOUBLE PRECISION NOT NULL DEFAULT 30,auto_water INTEGER NOT NULL DEFAULT 1,last_seen TEXT,last_watered_at TEXT,pump_until TEXT,schedule_enabled INTEGER NOT NULL DEFAULT 0,schedule_time TEXT,last_schedule_date TEXT,created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS readings(id BIGSERIAL PRIMARY KEY,device_id TEXT NOT NULL REFERENCES devices(device_id),soil_moisture DOUBLE PRECISION NOT NULL,temperature DOUBLE PRECISION NOT NULL,humidity DOUBLE PRECISION NOT NULL,light_level DOUBLE PRECISION NOT NULL,timestamp TEXT NOT NULL,water_tank_level DOUBLE PRECISION)",
        "CREATE INDEX IF NOT EXISTS idx_readings_device_time ON readings(device_id,timestamp DESC)",
        "CREATE TABLE IF NOT EXISTS watering_events(id BIGSERIAL PRIMARY KEY,device_id TEXT NOT NULL REFERENCES devices(device_id),trigger_type TEXT NOT NULL,moisture_before DOUBLE PRECISION,duration_seconds INTEGER NOT NULL,timestamp TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS alerts(id BIGSERIAL PRIMARY KEY,device_id TEXT NOT NULL REFERENCES devices(device_id),alert_type TEXT NOT NULL,level TEXT NOT NULL,message TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',created_at TEXT NOT NULL)",
    ]
    with connect() as c:
        for statement in statements: c.execute(statement)
        c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT ''")
        c.execute("ALTER TABLE devices ADD COLUMN IF NOT EXISTS user_id TEXT REFERENCES users(user_id)")
        c.execute("ALTER TABLE devices ADD COLUMN IF NOT EXISTS pump_until TEXT")
        c.execute("ALTER TABLE readings ADD COLUMN IF NOT EXISTS water_tank_level DOUBLE PRECISION")
        c.execute("ALTER TABLE devices ADD COLUMN IF NOT EXISTS schedule_enabled INTEGER NOT NULL DEFAULT 0")
        c.execute("ALTER TABLE devices ADD COLUMN IF NOT EXISTS schedule_time TEXT")
        c.execute("ALTER TABLE devices ADD COLUMN IF NOT EXISTS last_schedule_date TEXT")
        c.execute("INSERT INTO devices(device_id,plant_name,plant_type,location,moisture_threshold,created_at) VALUES(?,?,?,?,?,?) ON CONFLICT(device_id) DO NOTHING",("PLANT-001","Tomato Plant","tomato","Window sill",40,now_iso()))

def password_hash(password: str) -> str:
    salt=secrets.token_bytes(16)
    digest=hashlib.scrypt(password.encode("utf-8"),salt=salt,n=2**14,r=8,p=1,dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"

def password_matches(password: str, encoded: str) -> bool:
    try:
        algorithm,salt_hex,digest_hex=encoded.split("$",2)
        if algorithm!="scrypt": return False
        digest=hashlib.scrypt(password.encode("utf-8"),salt=bytes.fromhex(salt_hex),n=2**14,r=8,p=1,dklen=32)
        return secrets.compare_digest(digest.hex(),digest_hex)
    except (ValueError,TypeError): return False

def issue_session(c,user_id: str,response: Response,request_scheme: str):
    token=secrets.token_urlsafe(32)
    expires=datetime.now(timezone.utc)+timedelta(days=7)
    token_hash=hashlib.sha256(token.encode()).hexdigest()
    c.execute("INSERT INTO sessions(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)",(token_hash,user_id,expires.isoformat(),now_iso()))
    response.set_cookie("plant_session",token,httponly=True,samesite="strict",secure=request_scheme=="https",path="/",max_age=7*24*60*60)

def require_user(plant_session: str=Cookie(default="")):
    if not plant_session: raise HTTPException(401,"Sign in to continue")
    token_hash=hashlib.sha256(plant_session.encode()).hexdigest()
    with connect() as c:
        row=c.execute("SELECT users.user_id,users.name,users.email,sessions.expires_at FROM sessions JOIN users ON users.user_id=sessions.user_id WHERE sessions.token_hash=?",(token_hash,)).fetchone()
        if not row or datetime.fromisoformat(row["expires_at"])<=datetime.now(timezone.utc): raise HTTPException(401,"Session expired; sign in again")
        return {"user_id":row["user_id"],"name":row["name"],"email":row["email"]}

def require_owned_device(c,device_id: str,user_id: str):
    row=c.execute("SELECT * FROM devices WHERE device_id=? AND user_id=?",(device_id,user_id)).fetchone()
    if not row: raise HTTPException(404,"Device not found")
    return row

@app.post("/api/auth/register",status_code=201)
def register(payload: RegistrationIn,response: Response,request: Request):
    email=payload.email.strip().lower()
    user_id=secrets.token_hex(16)
    with connect() as c:
        existing=c.execute("SELECT user_id FROM users WHERE email=?",(email,)).fetchone()
        if existing: raise HTTPException(409,"An account with this email already exists")
        account_count=c.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
        c.execute("INSERT INTO users(user_id,name,email,password_hash,created_at) VALUES(?,?,?,?,?)",(user_id,payload.name.strip(),email,password_hash(payload.password),now_iso()))
        if account_count==0: c.execute("UPDATE devices SET user_id=? WHERE user_id IS NULL",(user_id,))
        issue_session(c,user_id,response,request.url.scheme)
    return {"user_id":user_id,"name":payload.name.strip(),"email":email}

@app.post("/api/auth/login")
def login(payload: AccountIn,response: Response,request: Request):
    email=payload.email.strip().lower()
    with connect() as c:
        user=c.execute("SELECT user_id,name,email,password_hash FROM users WHERE email=?",(email,)).fetchone()
        if not user or not password_matches(payload.password,user["password_hash"]): raise HTTPException(401,"Email or password is incorrect")
        issue_session(c,user["user_id"],response,request.url.scheme)
        return {"user_id":user["user_id"],"name":user["name"],"email":user["email"]}

@app.get("/api/auth/me")
def auth_me(user=Depends(require_user)): return user

@app.post("/api/auth/logout")
def logout(plant_session: str=Cookie(default="")):
    if plant_session:
        token_hash=hashlib.sha256(plant_session.encode()).hexdigest()
        with connect() as c: c.execute("DELETE FROM sessions WHERE token_hash=?",(token_hash,))
    response=JSONResponse({"logged_out":True})
    response.delete_cookie("plant_session",path="/",httponly=True,samesite="strict")
    return response

@app.on_event("startup")
def startup():
    if DATABASE_URL: init_postgres()
    else: init_db()

@app.get("/")
def dashboard(): return FileResponse(ROOT / "frontend" / "index.html")
app.mount("/static", StaticFiles(directory=ROOT / "frontend"), name="static")

@app.get("/api/health")
def health(): return {"status":"ok","service":"plant-care-api","time":now_iso()}

@app.get("/api/plant-profiles")
def plant_profiles():
    from automation.plant_profiles import PROFILES
    return PROFILES

@app.put("/api/devices/{device_id}/plant-profile")
def set_plant_profile(device_id: str, plant_type: str,user=Depends(require_user)):
    from automation.plant_profiles import PROFILES
    profile=PROFILES.get(plant_type.lower())
    if not profile: raise HTTPException(422,"Unknown plant profile")
    with connect() as c:
        require_owned_device(c,device_id,user["user_id"])
        cur=c.execute("UPDATE devices SET plant_type=?,moisture_threshold=? WHERE device_id=?",(plant_type.lower(),profile["moisture_threshold"],device_id))
        if not cur.rowcount: raise HTTPException(404,"Device not found")
        return {"device_id":device_id,"plant_type":plant_type.lower(),**profile}

def device_dict(r):
    d=dict(r); d.pop("user_id",None); d["auto_water"]=bool(d["auto_water"]); d["schedule_enabled"]=bool(d.get("schedule_enabled",0))
    last=d.get("last_seen")
    d["status"]="offline" if not last or datetime.now(timezone.utc)-datetime.fromisoformat(last)>timedelta(seconds=90) else "online"
    until=d.get("pump_until")
    d["pump_status"]=bool(until and datetime.now(timezone.utc)<datetime.fromisoformat(until))
    return d

def update_offline_alerts(c,user_id: str):
    """Create one offline alert per outage and resolve it after a new heartbeat."""
    rows=c.execute("SELECT device_id,plant_name,last_seen FROM devices WHERE user_id=?",(user_id,)).fetchall()
    now=datetime.now(timezone.utc)
    for row in rows:
        offline=bool(row["last_seen"] and now-datetime.fromisoformat(row["last_seen"])>timedelta(seconds=90))
        if offline:
            exists=c.execute("SELECT id FROM alerts WHERE device_id=? AND alert_type='DEVICE_OFFLINE' AND status='open'",(row["device_id"],)).fetchone()
            if not exists: c.execute("INSERT INTO alerts(device_id,alert_type,level,message,created_at) VALUES(?,?,?,?,?)",(row["device_id"],"DEVICE_OFFLINE","warning",f"{row['plant_name']} has not sent sensor data for more than 90 seconds.",now_iso()))
        else:
            c.execute("UPDATE alerts SET status='resolved' WHERE device_id=? AND alert_type='DEVICE_OFFLINE' AND status='open'",(row["device_id"],))

@app.get("/api/devices")
def devices(user=Depends(require_user)):
    with connect() as c:
        owner=user["user_id"]
        rows=c.execute("SELECT device_id,plant_name,last_seen FROM devices WHERE user_id=?",(owner,)).fetchall()
        now=datetime.now(timezone.utc)
        for row in rows:
            offline=bool(row["last_seen"] and now-datetime.fromisoformat(row["last_seen"])>timedelta(seconds=90))
            if offline:
                if not c.execute("SELECT id FROM alerts WHERE device_id=? AND alert_type='DEVICE_OFFLINE' AND status='open'",(row["device_id"],)).fetchone(): c.execute("INSERT INTO alerts(device_id,alert_type,level,message,created_at) VALUES(?,?,?,?,?)",(row["device_id"],"DEVICE_OFFLINE","warning",f"{row['plant_name']} has not sent sensor data for more than 90 seconds.",now_iso()))
            else: c.execute("UPDATE alerts SET status='resolved' WHERE device_id=? AND alert_type='DEVICE_OFFLINE' AND status='open'",(row["device_id"],))
        return [device_dict(r) for r in c.execute("SELECT * FROM devices WHERE user_id=? ORDER BY created_at",(owner,)).fetchall()]

def require_device_key(x_api_key: str = Header(default="")):
    if not secrets.compare_digest(x_api_key, DEVICE_API_KEY): raise HTTPException(status_code=401, detail="Invalid device API key")

@app.post("/api/devices", status_code=201)
def create_device(payload: DeviceIn,user=Depends(require_user)):
    from automation.plant_profiles import PROFILES
    profile=PROFILES.get(payload.plant_type.lower())
    threshold=payload.moisture_threshold if payload.moisture_threshold is not None else profile["moisture_threshold"] if profile else 30
    with connect() as c:
        try: c.execute("INSERT INTO devices(device_id,user_id,plant_name,plant_type,location,moisture_threshold,created_at) VALUES(?,?,?,?,?,?,?)", (payload.device_id,user["user_id"],payload.plant_name,payload.plant_type,payload.location,threshold,now_iso()))
        except sqlite3.IntegrityError: raise HTTPException(409,"Device already exists")
        return device_dict(c.execute("SELECT * FROM devices WHERE device_id=?",(payload.device_id,)).fetchone())

@app.get("/api/devices/{device_id}")
def get_device(device_id: str,user=Depends(require_user)):
    with connect() as c:
        r=require_owned_device(c,device_id,user["user_id"])
        if not r: raise HTTPException(404,"Device not found")
        update_offline_alerts(c,user["user_id"])
        return device_dict(r)

@app.put("/api/devices/{device_id}/schedule")
def set_schedule(device_id: str, payload: ScheduleIn,user=Depends(require_user)):
    with connect() as c:
        require_owned_device(c,device_id,user["user_id"])
        cur=c.execute("UPDATE devices SET schedule_enabled=?,schedule_time=? WHERE device_id=?",(int(payload.enabled),payload.time,device_id))
        if not cur.rowcount: raise HTTPException(404,"Device not found")
        return {"device_id":device_id,"schedule_enabled":payload.enabled,"schedule_time":payload.time}

@app.post("/api/sensors/data", status_code=201)
def ingest(payload: ReadingIn, response: Response, _: None=Depends(require_device_key)):
    ts=(payload.timestamp or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    with connect() as c:
        dev=c.execute("SELECT * FROM devices WHERE device_id=?",(payload.device_id,)).fetchone()
        if not dev: raise HTTPException(404,"Unknown device; register it first")
        existing=c.execute("SELECT id FROM readings WHERE device_id=? AND timestamp=?",(payload.device_id,ts)).fetchone()
        if existing:
            response.status_code=200
            return {"accepted":True,"duplicate":True,"device_id":payload.device_id,"timestamp":ts,"reading_id":existing["id"],"watering_event":None}
        c.execute("INSERT INTO readings(device_id,soil_moisture,temperature,humidity,light_level,timestamp,water_tank_level) VALUES(?,?,?,?,?,?,?)", (payload.device_id,payload.soil_moisture,payload.temperature,payload.humidity,payload.light_level,ts,payload.water_tank_level))
        c.execute("UPDATE devices SET last_seen=? WHERE device_id=?",(now_iso(),payload.device_id))
        if payload.soil_moisture < dev["moisture_threshold"]:
            open_alert=c.execute("SELECT id FROM alerts WHERE device_id=? AND alert_type='LOW_MOISTURE' AND status='open'",(payload.device_id,)).fetchone()
            if not open_alert: c.execute("INSERT INTO alerts(device_id,alert_type,level,message,created_at) VALUES(?,?,?,?,?)",(payload.device_id,"LOW_MOISTURE","warning",f"{dev['plant_name']} moisture is below {dev['moisture_threshold']:.0f}%.",now_iso()))
        else: c.execute("UPDATE alerts SET status='resolved' WHERE device_id=? AND alert_type='LOW_MOISTURE' AND status='open'",(payload.device_id,))
        if payload.water_tank_level is not None and payload.water_tank_level <= 10:
            if not c.execute("SELECT id FROM alerts WHERE device_id=? AND alert_type='LOW_WATER_TANK' AND status='open'",(payload.device_id,)).fetchone(): c.execute("INSERT INTO alerts(device_id,alert_type,level,message,created_at) VALUES(?,?,?,?,?)",(payload.device_id,"LOW_WATER_TANK","warning",f"{dev['plant_name']} water tank is low ({payload.water_tank_level:.0f}%). Automatic watering is paused.",now_iso()))
        else: c.execute("UPDATE alerts SET status='resolved' WHERE device_id=? AND alert_type='LOW_WATER_TANK' AND status='open'",(payload.device_id,))
        if payload.temperature > 35:
            if not c.execute("SELECT id FROM alerts WHERE device_id=? AND alert_type='HIGH_TEMPERATURE' AND status='open'",(payload.device_id,)).fetchone(): c.execute("INSERT INTO alerts(device_id,alert_type,level,message,created_at) VALUES(?,?,?,?,?)",(payload.device_id,"HIGH_TEMPERATURE","warning","Temperature exceeded 35°C.",now_iso()))
        else: c.execute("UPDATE alerts SET status='resolved' WHERE device_id=? AND alert_type='HIGH_TEMPERATURE' AND status='open'",(payload.device_id,))
        event=None
        local_now=datetime.now().astimezone()
        schedule_due=bool(dev["schedule_enabled"] and dev["schedule_time"]==local_now.strftime("%H:%M") and dev["last_schedule_date"]!=local_now.date().isoformat())
        latest=c.execute("SELECT timestamp FROM watering_events WHERE device_id=? ORDER BY id DESC LIMIT 1",(payload.device_id,)).fetchone()
        cooldown_ok=not latest or datetime.now(timezone.utc)-datetime.fromisoformat(latest[0])>timedelta(minutes=2)
        tank_allows_watering = payload.water_tank_level is None or payload.water_tank_level > 10
        if schedule_due:
            c.execute("UPDATE devices SET last_schedule_date=? WHERE device_id=?",(local_now.date().isoformat(),payload.device_id))
            if tank_allows_watering and cooldown_ok:
                c.execute("INSERT INTO watering_events(device_id,trigger_type,moisture_before,duration_seconds,timestamp) VALUES(?,?,?,?,?)",(payload.device_id,"scheduled",payload.soil_moisture,3,now_iso()))
                watered_at=now_iso(); c.execute("UPDATE devices SET last_watered_at=?,pump_until=? WHERE device_id=?",(watered_at,(datetime.now(timezone.utc)+timedelta(seconds=3)).isoformat(),payload.device_id)); event={"trigger_type":"scheduled","duration_seconds":3}
        if event is None and dev["auto_water"] and tank_allows_watering and should_water(payload.soil_moisture,dev["moisture_threshold"],cooldown_ok):
            c.execute("INSERT INTO watering_events(device_id,trigger_type,moisture_before,duration_seconds,timestamp) VALUES(?,?,?,?,?)",(payload.device_id,"automatic",payload.soil_moisture,3,now_iso()))
            watered_at=now_iso()
            c.execute("UPDATE devices SET last_watered_at=?,pump_until=? WHERE device_id=?",(watered_at,(datetime.now(timezone.utc)+timedelta(seconds=3)).isoformat(),payload.device_id)); event={"trigger_type":"automatic","duration_seconds":3}
        c.commit()
    return {"accepted":True,"duplicate":False,"device_id":payload.device_id,"timestamp":ts,"watering_event":event}

@app.get("/api/devices/{device_id}/device-state")
def device_state(device_id: str, after_id: int=Query(default=0,ge=0), _: None=Depends(require_device_key)):
    """Device-key endpoint used by the simulator to read state and new watering actions."""
    with connect() as c:
        if not c.execute("SELECT device_id FROM devices WHERE device_id=?",(device_id,)).fetchone(): raise HTTPException(404,"Unknown device")
        reading=c.execute("SELECT * FROM readings WHERE device_id=? ORDER BY timestamp DESC,id DESC LIMIT 1",(device_id,)).fetchone()
        action_cutoff=(datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()
        actions=c.execute("SELECT id,trigger_type,moisture_before,duration_seconds,timestamp FROM watering_events WHERE device_id=? AND id>? AND timestamp>=? ORDER BY id ASC LIMIT 100",(device_id,after_id,action_cutoff)).fetchall()
        latest=c.execute("SELECT MAX(id) AS latest_id FROM watering_events WHERE device_id=?",(device_id,)).fetchone()["latest_id"]
        return {"device_id":device_id,"reading":dict(reading) if reading else None,"watering_actions":[dict(row) for row in actions],"latest_action_id":latest or 0}

@app.get("/api/devices/{device_id}/latest")
def latest(device_id: str,user=Depends(require_user)):
    with connect() as c:
        require_owned_device(c,device_id,user["user_id"])
        row=c.execute("SELECT * FROM readings WHERE device_id=? ORDER BY timestamp DESC,id DESC LIMIT 1",(device_id,)).fetchone()
        if not row: return {"device_id":device_id,"reading":None}
        return {"device_id":device_id,"reading":dict(row)}

@app.get("/api/devices/{device_id}/history")
def history(device_id: str, limit: int=Query(default=100, ge=1, le=500),user=Depends(require_user)):
    with connect() as c:
        require_owned_device(c,device_id,user["user_id"])
        return [dict(r) for r in c.execute("SELECT * FROM readings WHERE device_id=? ORDER BY timestamp DESC,id DESC LIMIT ?",(device_id,limit)).fetchall()][::-1]

@app.put("/api/devices/{device_id}/threshold")
def set_threshold(device_id: str, payload: ThresholdIn,user=Depends(require_user)):
    with connect() as c:
        require_owned_device(c,device_id,user["user_id"])
        cur=c.execute("UPDATE devices SET moisture_threshold=? WHERE device_id=?",(payload.moisture_threshold,device_id))
        if cur.rowcount==0: raise HTTPException(404,"Device not found")
        return {"device_id":device_id,"moisture_threshold":payload.moisture_threshold}

@app.put("/api/devices/{device_id}/auto-water")
def set_auto(device_id: str, enabled: bool,user=Depends(require_user)):
    with connect() as c:
        require_owned_device(c,device_id,user["user_id"])
        cur=c.execute("UPDATE devices SET auto_water=? WHERE device_id=?",(int(enabled),device_id))
        if not cur.rowcount: raise HTTPException(404,"Device not found")
        return {"device_id":device_id,"auto_water":enabled}

@app.post("/api/devices/{device_id}/water",status_code=201)
def water(device_id: str, payload: WaterIn=WaterIn(),user=Depends(require_user)):
    with connect() as c:
        require_owned_device(c,device_id,user["user_id"])
        dev=c.execute("SELECT * FROM devices WHERE device_id=?",(device_id,)).fetchone()
        if not dev: raise HTTPException(404,"Device not found")
        if dev["pump_until"] and datetime.now(timezone.utc)<datetime.fromisoformat(dev["pump_until"]): raise HTTPException(409,"The virtual pump pulse is already running")
        latest=c.execute("SELECT water_tank_level FROM readings WHERE device_id=? ORDER BY timestamp DESC,id DESC LIMIT 1",(device_id,)).fetchone()
        if latest and latest["water_tank_level"] is not None and latest["water_tank_level"] <= 10: raise HTTPException(409,"Watering is blocked because the tank level is low")
        c.execute("INSERT INTO watering_events(device_id,trigger_type,moisture_before,duration_seconds,timestamp) VALUES(?,?,?,?,?)",(device_id,"manual",None,payload.duration_seconds,now_iso()))
        watered_at=now_iso()
        c.execute("UPDATE devices SET last_watered_at=?,pump_until=? WHERE device_id=?",(watered_at,(datetime.now(timezone.utc)+timedelta(seconds=payload.duration_seconds)).isoformat(),device_id))
        return {"queued":True,"device_id":device_id,"duration_seconds":payload.duration_seconds}

@app.get("/api/devices/{device_id}/analytics")
def analytics(device_id: str,user=Depends(require_user)):
    with connect() as c:
        require_owned_device(c,device_id,user["user_id"])
        dev=c.execute("SELECT moisture_threshold,last_seen FROM devices WHERE device_id=?",(device_id,)).fetchone()
        if not dev: raise HTTPException(404,"Device not found")
        row=c.execute("SELECT COUNT(*) AS samples,AVG(soil_moisture) AS avg_moisture,MIN(soil_moisture) AS min_moisture,MAX(soil_moisture) AS max_moisture,AVG(temperature) AS avg_temperature,AVG(humidity) AS avg_humidity FROM readings WHERE device_id=?",(device_id,)).fetchone()
        today_start=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0).isoformat()
        event_count=c.execute("SELECT COUNT(*) AS total FROM watering_events WHERE device_id=?",(device_id,)).fetchone()["total"]
        today_count=c.execute("SELECT COUNT(*) AS total FROM watering_events WHERE device_id=? AND timestamp>=?",(device_id,today_start)).fetchone()["total"]
        latest=c.execute("SELECT soil_moisture FROM readings WHERE device_id=? ORDER BY timestamp DESC,id DESC LIMIT 1",(device_id,)).fetchone()
        trend_rows=c.execute("SELECT soil_moisture,timestamp FROM readings WHERE device_id=? ORDER BY timestamp DESC,id DESC LIMIT 500",(device_id,)).fetchall()
        watering_forecast=estimate_watering([dict(item) for item in trend_rows],dev["moisture_threshold"],dev["last_seen"])
        status="offline" if not dev["last_seen"] or datetime.now(timezone.utc)-datetime.fromisoformat(dev["last_seen"])>timedelta(seconds=90) else "online"
        health="Waiting for readings" if not latest else "Needs water" if latest["soil_moisture"]<dev["moisture_threshold"] else "Healthy"
        return {"device_id":device_id,"threshold":dev["moisture_threshold"],"total_watering_events":event_count,"watering_events_today":today_count,"plant_health":health,"device_status":status,"last_seen":dev["last_seen"],"watering_forecast":watering_forecast,**dict(row)}

@app.get("/api/devices/{device_id}/watering-history")
def watering_history(device_id: str,user=Depends(require_user)):
    with connect() as c:
        require_owned_device(c,device_id,user["user_id"])
        return [dict(r) for r in c.execute("SELECT * FROM watering_events WHERE device_id=? ORDER BY id DESC LIMIT 100",(device_id,)).fetchall()]

@app.get("/api/alerts")
def alerts(status: Optional[str]=None,user=Depends(require_user)):
    with connect() as c:
        rows=c.execute("SELECT alerts.* FROM alerts JOIN devices USING(device_id) WHERE devices.user_id=? AND alerts.status=? ORDER BY alerts.id DESC LIMIT 100",(user["user_id"],status)).fetchall() if status else c.execute("SELECT alerts.* FROM alerts JOIN devices USING(device_id) WHERE devices.user_id=? ORDER BY alerts.id DESC LIMIT 100",(user["user_id"],)).fetchall()
        return [dict(r) for r in rows]

@app.put("/api/alerts/{alert_id}/acknowledge")
def acknowledge(alert_id: int,user=Depends(require_user)):
    with connect() as c:
        cur=c.execute("UPDATE alerts SET status='acknowledged' WHERE id=? AND status='open' AND device_id IN (SELECT device_id FROM devices WHERE user_id=?)",(alert_id,user["user_id"]))
        if not cur.rowcount: raise HTTPException(404,"Open alert not found")
        return {"id":alert_id,"status":"acknowledged"}
