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

def test_http_probe_real_container_juiceshop():
    # 1. Create scan & run ffuf for Juice Shop
    scan_resp = client.post("/scans", json={"target_url": "http://localhost:3000"})
    scan_id = scan_resp.json()["id"]

    ffuf_resp = client.post(f"/scans/{scan_id}/ffuf")
    assert ffuf_resp.status_code == 200
    nodes = ffuf_resp.json()["nodes"]
    assert len(nodes) > 0

    # Pick /robots.txt node
    target_node = next(n for n in nodes if n["properties"]["path"] == "/robots.txt")

    # 2. Trigger HTTP probe against /robots.txt node
    probe_resp = client.post(f"/scans/{scan_id}/nodes/{target_node['id']}/probe")
    assert probe_resp.status_code == 200

    data = probe_resp.json()
    assert data["scan_id"] == scan_id
    assert data["node_id"] == target_node["id"]
    assert data["evidence"]["tool_name"] == "http_probe"
    assert data["evidence"]["node_id"] == target_node["id"]

    raw_output = data["evidence"]["raw_output"]
    assert "HTTP/" in raw_output
    assert "User-agent: *" in raw_output or "Disallow:" in raw_output

def test_http_probe_real_container_dvwa():
    # 1. Create scan & run ffuf for DVWA
    scan_resp = client.post("/scans", json={"target_url": "http://localhost:8080"})
    scan_id = scan_resp.json()["id"]

    ffuf_resp = client.post(f"/scans/{scan_id}/ffuf")
    assert ffuf_resp.status_code == 200
    nodes = ffuf_resp.json()["nodes"]
    assert len(nodes) > 0

    # Pick /login.php node
    target_node = next(n for n in nodes if n["properties"]["path"] == "/login.php")

    # 2. Trigger HTTP probe against /login.php node
    probe_resp = client.post(f"/scans/{scan_id}/nodes/{target_node['id']}/probe")
    assert probe_resp.status_code == 200

    data = probe_resp.json()
    assert data["scan_id"] == scan_id
    assert data["node_id"] == target_node["id"]
    assert data["evidence"]["tool_name"] == "http_probe"

    raw_output = data["evidence"]["raw_output"]
    assert "HTTP/" in raw_output
    assert "200" in raw_output

def test_http_probe_cross_scan_rejection():
    # 1. Create Scan A and Scan B
    scan_a = client.post("/scans", json={"target_url": "http://localhost:3000"}).json()["id"]
    scan_b = client.post("/scans", json={"target_url": "http://localhost:8080"}).json()["id"]

    # Run ffuf on Scan B to generate nodes belonging to Scan B
    ffuf_b_nodes = client.post(f"/scans/{scan_b}/ffuf").json()["nodes"]
    node_from_scan_b = ffuf_b_nodes[0]

    # 2. Attempt to probe Scan B's node using Scan A's ID
    probe_resp = client.post(f"/scans/{scan_a}/nodes/{node_from_scan_b['id']}/probe")
    
    # Must return HTTP 403 Forbidden with Security Violation
    assert probe_resp.status_code == 403
    assert "Security Violation" in probe_resp.json()["detail"]
