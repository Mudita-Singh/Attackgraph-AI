import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.database import Base, get_db
from api.main import app

from sqlalchemy.pool import StaticPool

# In-memory SQLite DB for fast unit testing
SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

def test_ffuf_scan_nonexistent_scan_id():
    response = client.post("/scans/nonexistent-uuid-12345/ffuf")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]

def test_ffuf_scan_real_container_juiceshop():
    # 1. Create scan for Juice Shop
    scan_resp = client.post("/scans", json={"target_url": "http://localhost:3000"})
    assert scan_resp.status_code == 201
    scan_id = scan_resp.json()["id"]

    # 2. Trigger ffuf scan
    ffuf_resp = client.post(f"/scans/{scan_id}/ffuf")
    assert ffuf_resp.status_code == 200

    data = ffuf_resp.json()
    assert data["scan_id"] == scan_id
    assert "evidence" in data
    assert data["evidence"]["tool_name"] == "ffuf"
    assert "parsed_findings" in data["evidence"]
    assert "endpoints" in data["evidence"]["parsed_findings"]
    assert "calibration_baseline_size" in data["evidence"]["parsed_findings"]
    assert data["evidence"]["parsed_findings"]["calibration_baseline_size"] == 9393

    nodes = data["nodes"]
    # With SPA catch-all calibration filtering, false positives (9393 bytes) are filtered out
    assert len(nodes) < 10
    paths_found = [n["properties"]["path"] for n in nodes]
    assert "/robots.txt" in paths_found or "/assets" in paths_found


def test_ffuf_scan_real_container_dvwa():
    # 1. Create scan for DVWA
    scan_resp = client.post("/scans", json={"target_url": "http://localhost:8080"})
    assert scan_resp.status_code == 201
    scan_id = scan_resp.json()["id"]

    # 2. Trigger ffuf scan
    ffuf_resp = client.post(f"/scans/{scan_id}/ffuf")
    assert ffuf_resp.status_code == 200

    data = ffuf_resp.json()
    assert data["scan_id"] == scan_id
    assert "evidence" in data
    assert data["evidence"]["tool_name"] == "ffuf"

    nodes = data["nodes"]
    assert len(nodes) > 0

    paths_found = [n["properties"]["path"] for n in nodes]
    assert any(p in paths_found for p in ["/login.php", "/robots.txt", "/favicon.ico"])

    for n in nodes:
        assert n["node_type"] == "endpoint"

def test_ffuf_scan_missing_binary_fails_loudly(monkeypatch):
    import tools.ffuf
    monkeypatch.setattr(tools.ffuf, "get_ffuf_binary", lambda: None)

    scan_resp = client.post("/scans", json={"target_url": "http://localhost:3000"})
    scan_id = scan_resp.json()["id"]

    ffuf_resp = client.post(f"/scans/{scan_id}/ffuf")
    assert ffuf_resp.status_code == 500
    assert "ffuf binary not found" in ffuf_resp.json()["detail"]
