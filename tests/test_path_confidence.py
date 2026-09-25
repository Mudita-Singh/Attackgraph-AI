import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.database import Base, get_db
from db.models import Scan, Node, Edge
from api.main import app
from graph.confidence import (
    get_confidence_rationale,
    calculate_path_confidence,
    find_all_paths_to_node,
    CONFIDENCE_RATIONALE_TABLE
)

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


def test_get_confidence_rationale_lookup():
    # Test lookup for exact pattern key
    info = get_confidence_rationale("aws_access_key")
    assert info["confidence"] == 0.95
    assert "AKIA" in info["justification"]
    assert info["pattern_key"] == "aws_access_key"

    # Test lookup for reflected input
    info_refl = get_confidence_rationale("reflected_input:unencoded_html_context")
    assert info_refl["confidence"] == 0.55

    # Test unknown key fallback
    info_unknown = get_confidence_rationale("unknown_custom_pattern")
    assert info_unknown["confidence"] == 0.50
    assert "Unspecified" in info_unknown["justification"]


def test_calculate_path_confidence_weakest_link_rule():
    """
    Construct a 3-edge path (4 nodes) with edge confidences 0.95, 0.90, 0.40
    matching Section 11.3 worked example: min(0.95, 0.90, 0.40) = 0.40.
    """
    db = TestingSessionLocal()
    scan = Scan(target_url="http://localhost:3000", status="COMPLETED")
    db.add(scan)
    db.commit()

    n1 = Node(scan_id=scan.id, label="Service: http (3000)", node_type="service")
    n2 = Node(scan_id=scan.id, label="Endpoint: /api/config", node_type="endpoint")
    n3 = Node(scan_id=scan.id, label="Finding: Exposed Config", node_type="finding")
    n4 = Node(scan_id=scan.id, label="Secret: AWS Key", node_type="secret")
    db.add_all([n1, n2, n3, n4])
    db.commit()

    e1 = Edge(scan_id=scan.id, source_node_id=n1.id, target_node_id=n2.id, relation_type="EXPOSES", confidence=0.95, status="verified", pattern_key="ffuf")
    e2 = Edge(scan_id=scan.id, source_node_id=n2.id, target_node_id=n3.id, relation_type="LEADS_TO", confidence=0.90, status="verified", pattern_key="http_probe")
    e3 = Edge(scan_id=scan.id, source_node_id=n3.id, target_node_id=n4.id, relation_type="CONTAINS_SECRET", confidence=0.40, status="unverified", reasoning="Weak regex match", pattern_key="weak_pattern")
    db.add_all([e1, e2, e3])
    db.commit()

    path_nodes = [n1.id, n2.id, n3.id, n4.id]
    result = calculate_path_confidence(path_nodes, db)

    assert result["path_confidence"] == 0.40
    assert result["edge_confidences"] == [0.95, 0.90, 0.40]
    assert result["weakest_edge"]["id"] == e3.id
    assert result["weakest_edge"]["confidence"] == 0.40
    assert result["weakest_edge"]["reasoning"] == "Weak regex match"
    assert result["path"] == [
        "Service: http (3000)",
        "Endpoint: /api/config",
        "Finding: Exposed Config",
        "Secret: AWS Key"
    ]
    db.close()


def test_calculate_path_confidence_disconnected_path_raises():
    """
    Test that an ordered list of nodes with no connecting edge between a consecutive pair
    raises a clear ValueError.
    """
    db = TestingSessionLocal()
    scan = Scan(target_url="http://localhost:3000", status="COMPLETED")
    db.add(scan)
    db.commit()

    n1 = Node(scan_id=scan.id, label="Node A", node_type="service")
    n2 = Node(scan_id=scan.id, label="Node B", node_type="endpoint")
    n3 = Node(scan_id=scan.id, label="Node C (Disconnected)", node_type="secret")
    db.add_all([n1, n2, n3])
    db.commit()

    # Edge exists between n1 -> n2, but NO edge exists between n2 -> n3
    e1 = Edge(scan_id=scan.id, source_node_id=n1.id, target_node_id=n2.id, relation_type="EXPOSES", confidence=0.95, status="verified")
    db.add(e1)
    db.commit()

    with pytest.raises(ValueError) as exc_info:
        calculate_path_confidence([n1.id, n2.id, n3.id], db)

    assert "No connecting edge found between node" in str(exc_info.value)
    db.close()


def test_find_all_paths_to_node_multiple_paths():
    """
    Test graph traversal to find all paths from root nodes to target node.
    Construct graph with two separate paths reaching the same target node:
    Path 1: Root A -> Node B -> Target T
    Path 2: Root C -> Target T
    """
    db = TestingSessionLocal()
    scan = Scan(target_url="http://localhost:3000", status="COMPLETED")
    db.add(scan)
    db.commit()

    nA = Node(scan_id=scan.id, label="Root A", node_type="service")
    nB = Node(scan_id=scan.id, label="Node B", node_type="endpoint")
    nC = Node(scan_id=scan.id, label="Root C", node_type="service")
    nT = Node(scan_id=scan.id, label="Target Node T", node_type="secret")
    db.add_all([nA, nB, nC, nT])
    db.commit()

    eA_B = Edge(scan_id=scan.id, source_node_id=nA.id, target_node_id=nB.id, relation_type="EXPOSES", confidence=1.0, status="verified")
    eB_T = Edge(scan_id=scan.id, source_node_id=nB.id, target_node_id=nT.id, relation_type="LEADS_TO", confidence=0.40, status="unverified")
    eC_T = Edge(scan_id=scan.id, source_node_id=nC.id, target_node_id=nT.id, relation_type="EXPOSES", confidence=0.85, status="verified")
    db.add_all([eA_B, eB_T, eC_T])
    db.commit()

    paths = find_all_paths_to_node(nT.id, scan.id, db)
    assert len(paths) == 2

    path_node_ids = set(tuple(p) for p in paths)
    expected_path_1 = (nA.id, nB.id, nT.id)
    expected_path_2 = (nC.id, nT.id)

    assert expected_path_1 in path_node_ids
    assert expected_path_2 in path_node_ids
    db.close()


def test_api_get_path_confidence_endpoint_sorting():
    """
    Integration test for GET /scans/{scan_id}/nodes/{node_id}/path-confidence.
    Verifies response is returned sorted by path_confidence descending.
    Path 1 confidence = min(1.0, 0.40) = 0.40
    Path 2 confidence = min(0.85) = 0.85
    Sorted result should have Path 2 (0.85) first, then Path 1 (0.40).
    """
    db = TestingSessionLocal()
    scan = Scan(target_url="http://localhost:3000", status="COMPLETED")
    db.add(scan)
    db.commit()
    scan_id = scan.id

    nA = Node(scan_id=scan_id, label="Root Service A", node_type="service")
    nB = Node(scan_id=scan_id, label="Endpoint B", node_type="endpoint")
    nC = Node(scan_id=scan_id, label="Root Service C", node_type="service")
    nT = Node(scan_id=scan_id, label="Target Secret Node", node_type="secret")
    db.add_all([nA, nB, nC, nT])
    db.commit()
    db.refresh(nA)
    db.refresh(nB)
    db.refresh(nC)
    db.refresh(nT)

    eA_B = Edge(scan_id=scan_id, source_node_id=nA.id, target_node_id=nB.id, relation_type="EXPOSES", confidence=1.0, status="verified")
    eB_T = Edge(scan_id=scan_id, source_node_id=nB.id, target_node_id=nT.id, relation_type="LEADS_TO", confidence=0.40, status="unverified")
    eC_T = Edge(scan_id=scan_id, source_node_id=nC.id, target_node_id=nT.id, relation_type="EXPOSES", confidence=0.85, status="verified")
    db.add_all([eA_B, eB_T, eC_T])
    db.commit()
    nA_id, nB_id, nC_id, nT_id = nA.id, nB.id, nC.id, nT.id
    db.close()

    response = client.get(f"/scans/{scan_id}/nodes/{nT_id}/path-confidence")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2

    # Verify descending sort order: first item is path_confidence 0.85, second is 0.40
    assert data[0]["path_confidence"] == 0.85
    assert data[0]["node_ids"] == [nC_id, nT_id]
    assert data[0]["weakest_edge"]["confidence"] == 0.85

    assert data[1]["path_confidence"] == 0.40
    assert data[1]["node_ids"] == [nA_id, nB_id, nT_id]
    assert data[1]["weakest_edge"]["confidence"] == 0.40


def test_api_get_path_confidence_cross_scan_scoping_forbidden():
    db = TestingSessionLocal()
    scan1 = Scan(target_url="http://localhost:3000", status="COMPLETED")
    scan2 = Scan(target_url="http://localhost:8080", status="COMPLETED")
    db.add_all([scan1, scan2])
    db.commit()
    db.refresh(scan1)
    db.refresh(scan2)

    n_scan2 = Node(scan_id=scan2.id, label="Node scan 2", node_type="endpoint")
    db.add(n_scan2)
    db.commit()
    db.refresh(n_scan2)
    scan1_id = scan1.id
    n_scan2_id = n_scan2.id
    db.close()

    # Querying scan2's node under scan1 MUST return HTTP 403 Forbidden
    response = client.get(f"/scans/{scan1_id}/nodes/{n_scan2_id}/path-confidence")
    assert response.status_code == 403
    assert "Security Violation" in response.json()["detail"]

