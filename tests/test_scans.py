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

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

# --- Legitimate Allowed Targets ---

def test_create_scan_allowed_target_juiceshop():
    response = client.post("/scans", json={"target_url": "http://localhost:3000"})
    assert response.status_code == 201
    data = response.json()
    assert data["target_url"] == "http://localhost:3000"
    assert data["status"] == "INITIALIZED"

def test_create_scan_allowed_target_dvwa():
    response = client.post("/scans", json={"target_url": "http://localhost:8080"})
    assert response.status_code == 201
    data = response.json()
    assert data["target_url"] == "http://localhost:8080"
    assert data["status"] == "INITIALIZED"

def test_create_scan_allowed_target_ip():
    response = client.post("/scans", json={"target_url": "http://127.0.0.1:3000"})
    assert response.status_code == 201
    data = response.json()
    assert data["target_url"] == "http://127.0.0.1:3000"
    assert data["status"] == "INITIALIZED"

# --- Allowlist Security Edge Cases (Must return HTTP 403 Forbidden, NEVER 500 or 201) ---

def test_edge_case_subdomain_bypass():
    # http://localhost:3000.evil.com -> Malformed port/host string
    response = client.post("/scans", json={"target_url": "http://localhost:3000.evil.com"})
    assert response.status_code == 403
    assert "Security Violation" in response.json()["detail"]

def test_edge_case_userinfo_authority_bypass():
    # http://localhost:3000@evil.com -> Embedded credentials in authority
    response = client.post("/scans", json={"target_url": "http://localhost:3000@evil.com"})
    assert response.status_code == 403
    assert "Security Violation" in response.json()["detail"]

def test_edge_case_path_injection_url():
    # http://evil.com/http://localhost:3000 -> Allowed URL in path
    response = client.post("/scans", json={"target_url": "http://evil.com/http://localhost:3000"})
    assert response.status_code == 403
    assert "Security Violation" in response.json()["detail"]

def test_edge_case_path_traversal():
    # http://localhost:3000/../../etc/passwd -> Path traversal attempt
    response = client.post("/scans", json={"target_url": "http://localhost:3000/../../etc/passwd"})
    assert response.status_code == 403
    assert "Security Violation" in response.json()["detail"]

def test_create_scan_disallowed_target():
    response = client.post("/scans", json={"target_url": "http://example.com"})
    assert response.status_code == 403
    assert "Security Violation" in response.json()["detail"]

def test_create_scan_disallowed_arbitrary_ip():
    response = client.post("/scans", json={"target_url": "http://192.168.1.1:8080"})
    assert response.status_code == 403
    assert "Security Violation" in response.json()["detail"]
