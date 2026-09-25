import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.database import Base, get_db
from db.models import Scan, Node, Edge, Evidence
from api.main import app

# In-memory SQLite DB for fast isolated unit testing
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

def test_get_scan_graph_empty():
    scan_resp = client.post("/scans", json={"target_url": "http://localhost:3000"})
    assert scan_resp.status_code == 201
    scan_id = scan_resp.json()["id"]

    response = client.get(f"/scans/{scan_id}/graph")
    assert response.status_code == 200
    data = response.json()
    assert data["scan_id"] == scan_id
    assert data["nodes"] == []
    assert data["edges"] == []

def test_get_scan_graph_not_found():
    response = client.get("/scans/non-existent-scan-id/graph")
    assert response.status_code == 404
    assert response.json()["detail"] == "Scan not found"

def test_get_scan_graph_with_data():
    db = next(override_get_db())
    scan = Scan(target_url="http://localhost:3000", status="COMPLETED")
    db.add(scan)
    db.commit()
    db.refresh(scan)
    scan_id = scan.id

    n1 = Node(scan_id=scan_id, label="Service: http (port 3000)", node_type="service", is_critical=False, properties={"port": 3000})
    n2 = Node(scan_id=scan_id, label="Endpoint: /rest/user/login", node_type="endpoint", is_critical=True, properties={"path": "/rest/user/login"})
    db.add_all([n1, n2])
    db.commit()
    db.refresh(n1)
    db.refresh(n2)
    n1_id, n2_id = n1.id, n2.id

    e1 = Edge(
        scan_id=scan_id,
        source_node_id=n1_id,
        target_node_id=n2_id,
        relation_type="EXPOSES_ENDPOINT",
        confidence=0.9,
        status="verified",
        reasoning="ffuf endpoint discovery",
        pattern_key="ffuf_discovery"
    )
    db.add(e1)
    db.commit()
    db.refresh(e1)
    e1_id = e1.id

    ev1 = Evidence(
        scan_id=scan_id,
        node_id=n2_id,
        tool_name="http_probe",
        raw_output="HTTP/1.1 200 OK\nContent-Type: application/json\n\n{\"status\":\"success\"}",
        parsed_findings={"status_code": 200}
    )
    db.add(ev1)
    db.commit()
    db.refresh(ev1)
    ev1_id = ev1.id
    db.close()

    response = client.get(f"/scans/{scan_id}/graph")
    assert response.status_code == 200
    data = response.json()
    assert data["scan_id"] == scan_id
    assert len(data["nodes"]) == 2
    assert len(data["edges"]) == 1

    node2_res = next(n for n in data["nodes"] if n["id"] == n2_id)
    assert node2_res["label"] == "Endpoint: /rest/user/login"
    assert node2_res["node_type"] == "endpoint"
    assert node2_res["is_critical"] is True
    assert len(node2_res["evidence"]) == 1
    assert node2_res["evidence"][0]["id"] == ev1_id
    assert node2_res["evidence"][0]["tool_name"] == "http_probe"
    assert "raw_output" not in node2_res["evidence"][0]

    edge_res = data["edges"][0]
    assert edge_res["id"] == e1_id
    assert edge_res["source_node_id"] == n1_id
    assert edge_res["target_node_id"] == n2_id
    assert edge_res["relation_type"] == "EXPOSES_ENDPOINT"
    assert edge_res["confidence"] == 0.9
    assert edge_res["status"] == "verified"
    assert edge_res["reasoning"] == "ffuf endpoint discovery"
    assert edge_res["pattern_key"] == "ffuf_discovery"

def test_get_node_evidence_valid():
    db = next(override_get_db())
    scan = Scan(target_url="http://localhost:3000", status="COMPLETED")
    db.add(scan)
    db.commit()
    db.refresh(scan)
    scan_id = scan.id

    n1 = Node(scan_id=scan_id, label="Endpoint: /api/Users", node_type="endpoint", is_critical=False)
    db.add(n1)
    db.commit()
    db.refresh(n1)
    n1_id = n1.id

    ev1 = Evidence(
        scan_id=scan_id,
        node_id=n1_id,
        tool_name="access_control_check",
        raw_output="HTTP/1.1 200 OK\nBody: [{'id': 1}]",
        parsed_findings={"unauthenticated_access": True}
    )
    db.add(ev1)
    db.commit()
    db.refresh(ev1)
    ev1_id = ev1.id
    db.close()

    response = client.get(f"/scans/{scan_id}/nodes/{n1_id}/evidence")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == ev1_id
    assert data[0]["tool_name"] == "access_control_check"
    assert data[0]["raw_output"] == "HTTP/1.1 200 OK\nBody: [{'id': 1}]"
    assert data[0]["parsed_findings"] == {"unauthenticated_access": True}

def test_get_node_evidence_cross_scan_scoping_forbidden():
    db = next(override_get_db())
    scan1 = Scan(target_url="http://localhost:3000", status="COMPLETED")
    scan2 = Scan(target_url="http://localhost:8080", status="COMPLETED")
    db.add_all([scan1, scan2])
    db.commit()
    db.refresh(scan1)
    db.refresh(scan2)
    scan1_id, scan2_id = scan1.id, scan2.id

    node_scan2 = Node(scan_id=scan2_id, label="Node belonging to scan 2", node_type="endpoint")
    db.add(node_scan2)
    db.commit()
    db.refresh(node_scan2)
    node_scan2_id = node_scan2.id
    db.close()

    # Attempting to query node_scan2 using scan1's scan_id MUST return HTTP 403 Forbidden
    response = client.get(f"/scans/{scan1_id}/nodes/{node_scan2_id}/evidence")
    assert response.status_code == 403
    assert "Security Violation" in response.json()["detail"]

def test_get_node_evidence_not_found():
    db = next(override_get_db())
    scan = Scan(target_url="http://localhost:3000", status="COMPLETED")
    db.add(scan)
    db.commit()
    db.refresh(scan)
    scan_id = scan.id
    db.close()

    response = client.get(f"/scans/{scan_id}/nodes/non-existent-node/evidence")
    assert response.status_code == 404
    assert response.json()["detail"] == "Node not found"
