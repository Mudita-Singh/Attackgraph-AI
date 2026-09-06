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

def test_nmap_scan_nonexistent_scan_id():
    response = client.post("/scans/nonexistent-uuid-12345/nmap")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]

def test_nmap_scan_real_container_juiceshop():
    # 1. Create a scan for Juice Shop (http://localhost:3000)
    scan_resp = client.post("/scans", json={"target_url": "http://localhost:3000"})
    assert scan_resp.status_code == 201
    scan_id = scan_resp.json()["id"]

    # 2. Trigger Nmap scan against the real container
    nmap_resp = client.post(f"/scans/{scan_id}/nmap")
    assert nmap_resp.status_code == 200

    data = nmap_resp.json()
    assert data["scan_id"] == scan_id
    assert "evidence" in data
    assert data["evidence"]["tool_name"] == "nmap"
    assert "parsed_findings" in data["evidence"]
    assert "open_ports" in data["evidence"]["parsed_findings"]

    # Verify nodes created for open ports
    nodes = data["nodes"]
    assert len(nodes) > 0
    ports_found = [n["properties"]["port"] for n in nodes]
    assert 3000 in ports_found # Juice Shop container port
