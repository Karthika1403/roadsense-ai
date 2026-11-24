import os; os.environ["DATABASE_URL"] = "sqlite:///./test.db"
from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
def test_flow():
    c.post("/api/v1/auth/register", json={"email": "a@b.co", "password": "secret1"})
    tok = c.post("/api/v1/auth/login", data={"username": "a@b.co", "password": "secret1"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    vid = c.post("/api/v1/vehicles", json={"name": "Demo"}, headers=h).json()["id"]
    for _ in range(25): c.post(f"/api/v1/vehicles/{vid}/simulate", headers=h)
    r = c.post(f"/api/v1/vehicles/{vid}/simulate?fault=heat", headers=h).json()
    assert r["alerts"] and r["risk"]["level"] in ("low", "medium", "high")
    assert c.get(f"/api/v1/vehicles/{vid}/health", headers=h).json()["ride_health_score"] > 0
def test_auth_required(): assert c.get("/api/v1/vehicles").status_code == 401
