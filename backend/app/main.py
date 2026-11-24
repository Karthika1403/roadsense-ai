"""RoadSense AI API. Independent portfolio project, simulated data only."""
import os, hashlib, secrets, statistics, random
from datetime import datetime, timedelta
import jwt
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, Session

SECRET = os.getenv("SECRET_KEY", "dev-change-me")
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./roadsense.db")
engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True); email = Column(String, unique=True, index=True); password_hash = Column(String)
class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(Integer, primary_key=True); user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String); powertrain = Column(String, default="ice"); mileage_km = Column(Float, default=0)
class Reading(Base):
    __tablename__ = "sensor_readings"
    id = Column(Integer, primary_key=True); vehicle_id = Column(Integer, ForeignKey("vehicles.id"), index=True)
    ts = Column(DateTime, default=datetime.utcnow)
    engine_temp = Column(Float); rpm = Column(Float); battery_v = Column(Float); vibration = Column(Float)
    speed = Column(Float); load = Column(Float); data_origin = Column(String, default="roadsense_simulated")
class Alert(Base):
    __tablename__ = "anomaly_alerts"
    id = Column(Integer, primary_key=True); vehicle_id = Column(Integer, ForeignKey("vehicles.id"), index=True)
    ts = Column(DateTime, default=datetime.utcnow); sensor = Column(String); value = Column(Float); z = Column(Float); reason = Column(String)
Base.metadata.create_all(engine)

app = FastAPI(title="RoadSense AI", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS", "*").split(","), allow_methods=["*"], allow_headers=["*"])
oauth = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def db():
    s = SessionLocal()
    try: yield s
    finally: s.close()

def hash_pw(p, salt=None):
    salt = salt or secrets.token_hex(8)
    return salt + "$" + hashlib.pbkdf2_hmac("sha256", p.encode(), salt.encode(), 120_000).hex()
def check_pw(p, h): return secrets.compare_digest(hash_pw(p, h.split("$")[0]), h)
def make_token(uid): return jwt.encode({"sub": str(uid), "exp": datetime.utcnow() + timedelta(hours=12)}, SECRET, "HS256")
def current_user(tok: str = Depends(oauth), s: Session = Depends(db)):
    try: uid = int(jwt.decode(tok, SECRET, ["HS256"])["sub"])
    except Exception: raise HTTPException(401, "Invalid token")
    u = s.get(User, uid)
    if not u: raise HTTPException(401, "Unknown user")
    return u
def own_vehicle(vid, u, s):
    v = s.get(Vehicle, vid)
    if not v or v.user_id != u.id: raise HTTPException(404, "Vehicle not found")
    return v

class Creds(BaseModel): email: str = Field(min_length=5); password: str = Field(min_length=6)
class VehicleIn(BaseModel): name: str; powertrain: str = Field("ice", pattern="^(ice|ev)$")
class Telemetry(BaseModel):
    engine_temp: float = Field(ge=-20, le=200); rpm: float = Field(ge=0, le=20000)
    battery_v: float = Field(ge=0, le=60); vibration: float = Field(ge=0, le=20)
    speed: float = Field(0, ge=0, le=300); load: float = Field(0.5, ge=0, le=1)

@app.post("/api/v1/auth/register", status_code=201)
def register(c: Creds, s: Session = Depends(db)):
    if s.query(User).filter_by(email=c.email.lower()).first(): raise HTTPException(409, "Email taken")
    u = User(email=c.email.lower(), password_hash=hash_pw(c.password)); s.add(u); s.commit()
    return {"id": u.id}
@app.post("/api/v1/auth/login")
def login(f: OAuth2PasswordRequestForm = Depends(), s: Session = Depends(db)):
    u = s.query(User).filter_by(email=f.username.lower()).first()
    if not u or not check_pw(f.password, u.password_hash): raise HTTPException(401, "Bad credentials")
    return {"access_token": make_token(u.id), "token_type": "bearer"}

@app.post("/api/v1/vehicles", status_code=201)
def add_vehicle(v: VehicleIn, u: User = Depends(current_user), s: Session = Depends(db)):
    x = Vehicle(user_id=u.id, name=v.name, powertrain=v.powertrain); s.add(x); s.commit()
    return {"id": x.id, "name": x.name, "powertrain": x.powertrain}
@app.get("/api/v1/vehicles")
def list_vehicles(u: User = Depends(current_user), s: Session = Depends(db)):
    return [{"id": v.id, "name": v.name, "powertrain": v.powertrain} for v in s.query(Vehicle).filter_by(user_id=u.id)]

SENSORS = {"engine_temp": "Engine temp", "battery_v": "Battery voltage", "vibration": "Vibration"}
def detect(s, vid, r):
    hist = s.query(Reading).filter_by(vehicle_id=vid).order_by(Reading.id.desc()).limit(40).all()
    out = []
    if len(hist) < 20: return out
    for k in SENSORS:
        w = [getattr(h, k) for h in hist]; m = statistics.fmean(w); sd = statistics.pstdev(w) or 0.01
        z = (getattr(r, k) - m) / sd
        if abs(z) > 3:
            out.append(Alert(vehicle_id=vid, sensor=k, value=getattr(r, k), z=round(z, 2),
                             reason=f"{SENSORS[k]} deviates from last {len(w)} samples (|z|>3)"))
    return out

def clamp(x, a=0, b=100): return max(a, min(b, x))
def component_health(r):
    return {"engine": clamp(100 - (r.engine_temp - 95) * 3.5), "battery": clamp(100 - (13.9 - r.battery_v) * 45),
            "drivetrain": clamp(100 - (r.vibration - 1.2) * 30), "suspension": clamp(100 - (r.vibration - 1.5) * 18),
            "tyres": clamp(100 - (r.vibration - 1.0) * 22)}
def risk(r, comp):
    path = os.path.join(os.path.dirname(__file__), "ml_models", "risk.joblib")
    if os.path.exists(path):
        import joblib
        p = float(joblib.load(path).predict_proba([[r.engine_temp, r.rpm, r.battery_v, r.vibration, r.load]])[0][1])
        src = "ml_model"
    else:
        p = 1 - min(comp.values()) / 100; src = "rule_fallback"
    return {"failure_probability": round(p, 3), "level": "high" if p > .6 else "medium" if p > .3 else "low", "source": src}

@app.post("/api/v1/vehicles/{vid}/telemetry", status_code=201)
def telemetry(vid: int, t: Telemetry, u: User = Depends(current_user), s: Session = Depends(db)):
    own_vehicle(vid, u, s)
    r = Reading(vehicle_id=vid, engine_temp=t.engine_temp, rpm=t.rpm, battery_v=t.battery_v, vibration=t.vibration, speed=t.speed, load=t.load)
    alerts = detect(s, vid, r); s.add(r); s.add_all(alerts); s.commit()
    comp = component_health(r)
    return {"alerts": [a.reason for a in alerts], "components": comp, "risk": risk(r, comp), "data_origin": r.data_origin}
@app.get("/api/v1/vehicles/{vid}/health")
def health(vid: int, u: User = Depends(current_user), s: Session = Depends(db)):
    own_vehicle(vid, u, s)
    r = s.query(Reading).filter_by(vehicle_id=vid).order_by(Reading.id.desc()).first()
    if not r: raise HTTPException(404, "No telemetry yet")
    comp = component_health(r)
    return {"ride_health_score": round(statistics.fmean(comp.values()), 1), "components": comp, "risk": risk(r, comp)}
@app.get("/api/v1/vehicles/{vid}/alerts")
def alerts(vid: int, u: User = Depends(current_user), s: Session = Depends(db)):
    own_vehicle(vid, u, s)
    return [{"ts": a.ts, "sensor": a.sensor, "value": a.value, "z": a.z, "reason": a.reason}
            for a in s.query(Alert).filter_by(vehicle_id=vid).order_by(Alert.id.desc()).limit(50)]
@app.post("/api/v1/vehicles/{vid}/simulate")
def simulate(vid: int, fault: str = "", u: User = Depends(current_user), s: Session = Depends(db)):
    """Server-side ride simulator: one reading, optionally with an injected fault."""
    t = Telemetry(engine_temp=90 + random.gauss(0, 2) + (35 if fault == "heat" else 0),
                  rpm=random.gauss(3500, 400), battery_v=13.9 + random.gauss(0, .05) - (1.5 if fault == "batt" else 0),
                  vibration=abs(random.gauss(.9, .1)) + (1.6 if fault == "bear" else 0), speed=random.uniform(20, 90), load=random.random())
    return telemetry(vid, t, u, s)
@app.get("/health")
def ping(): return {"ok": True}
