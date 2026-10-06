import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.database import Base, get_db
from db.models import Scan, Node, Edge, AgentLog
from api.main import app

SQLALCHEMY_DATABASE_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_database():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

def test_get_scan_replay_not_found():
    response = client.get("/scans/non-existent-scan-id/replay")
    assert response.status_code == 404
    assert response.json()["detail"] == "Scan not found"

def test_get_scan_replay_manual_fixture_null_step_number():
    db = next(override_get_db())
    scan = Scan(target_url="http://localhost:3000", status="INITIALIZED")
    db.add(scan)
    db.commit()

    t0 = datetime.utcnow()
    n1 = Node(scan_id=scan.id, label="Service 3000", node_type="service", created_at=t0)
    n2 = Node(scan_id=scan.id, label="Endpoint /api", node_type="endpoint", created_at=t0 + timedelta(seconds=2))
    db.add_all([n1, n2])
    db.flush()
    e1 = Edge(scan_id=scan.id, source_node_id=n1.id, target_node_id=n2.id, relation_type="EXPOSES", created_at=t0 + timedelta(seconds=4))
    db.add(e1)
    db.commit()

    resp = client.get(f"/scans/{scan.id}/replay")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 3
    assert events[0]["event_type"] == "node_created"
    assert events[0]["data"]["id"] == n1.id
    assert events[0]["step_number"] is None

    assert events[1]["event_type"] == "node_created"
    assert events[1]["data"]["id"] == n2.id
    assert events[1]["step_number"] is None

    assert events[2]["event_type"] == "edge_created"
    assert events[2]["data"]["id"] == e1.id
    assert events[2]["step_number"] is None

def test_get_scan_replay_with_agent_logs():
    db = next(override_get_db())
    scan = Scan(target_url="http://localhost:3000", status="AGENT_LOOP_COMPLETED")
    db.add(scan)
    db.commit()

    t0 = datetime.utcnow()
    log1 = AgentLog(scan_id=scan.id, step_number=1, action="nmap_scan()", timestamp=t0)
    log2 = AgentLog(scan_id=scan.id, step_number=2, action="ffuf_scan()", timestamp=t0 + timedelta(seconds=10))
    db.add_all([log1, log2])
    db.commit()

    n1 = Node(scan_id=scan.id, label="Service Port 80", node_type="service", created_at=t0 + timedelta(seconds=1))
    n2 = Node(scan_id=scan.id, label="Endpoint /admin", node_type="endpoint", created_at=t0 + timedelta(seconds=12))
    db.add_all([n1, n2])
    db.flush()
    e1 = Edge(scan_id=scan.id, source_node_id=n1.id, target_node_id=n2.id, relation_type="EXPOSES", created_at=t0 + timedelta(seconds=15), step=2)
    db.add(e1)
    db.commit()

    resp = client.get(f"/scans/{scan.id}/replay")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 3

    assert events[0]["data"]["id"] == n1.id
    assert events[0]["step_number"] == 1

    assert events[1]["data"]["id"] == n2.id
    assert events[1]["step_number"] == 2

    assert events[2]["data"]["id"] == e1.id
    assert events[2]["step_number"] == 2
