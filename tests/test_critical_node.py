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
from db.models import Scan, Node, Edge
from api.main import app
from graph.critical_node import (
    calculate_node_impact,
    find_critical_node
)

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


def test_bottleneck_critical_node_and_leaf_zero_impact():
    """
    Unit test using a fixture graph where one node is an obvious bottleneck
    (one endpoint node that two separate downstream secret/finding nodes depend on exclusively).
    Confirms bottleneck is correctly identified as critical with score 2.
    Confirms removing a leaf node correctly scores 0 impact.
    """
    db = TestingSessionLocal()
    scan = Scan(target_url="http://localhost:3000", status="COMPLETED")
    db.add(scan)
    db.commit()

    n_root1 = Node(scan_id=scan.id, label="Root Service 1", node_type="service")
    n_root2 = Node(scan_id=scan.id, label="Root Service 2", node_type="service")
    n_bottleneck = Node(scan_id=scan.id, label="Endpoint Bottleneck", node_type="endpoint")
    n_secret1 = Node(scan_id=scan.id, label="AWS Secret 1", node_type="secret")
    n_secret2 = Node(scan_id=scan.id, label="AWS Secret 2", node_type="secret")
    db.add_all([n_root1, n_root2, n_bottleneck, n_secret1, n_secret2])
    db.commit()

    e1 = Edge(scan_id=scan.id, source_node_id=n_root1.id, target_node_id=n_bottleneck.id, relation_type="EXPOSES", status="verified")
    e2 = Edge(scan_id=scan.id, source_node_id=n_root2.id, target_node_id=n_bottleneck.id, relation_type="EXPOSES", status="verified")
    e3 = Edge(scan_id=scan.id, source_node_id=n_bottleneck.id, target_node_id=n_secret1.id, relation_type="LEAKS", status="verified")
    e4 = Edge(scan_id=scan.id, source_node_id=n_bottleneck.id, target_node_id=n_secret2.id, relation_type="LEAKS", status="verified")
    db.add_all([e1, e2, e3, e4])
    db.commit()

    # Test leaf node impact
    leaf_impact = calculate_node_impact(n_secret1.id, scan.id, db)
    assert leaf_impact["node_id"] == n_secret1.id
    assert leaf_impact["downstream_count"] == 0
    assert leaf_impact["nodes_disconnected_if_removed"] == []
    assert leaf_impact["disconnection_impact_score"] == 0

    # Test bottleneck node impact
    bottleneck_impact = calculate_node_impact(n_bottleneck.id, scan.id, db)
    assert bottleneck_impact["node_id"] == n_bottleneck.id
    assert bottleneck_impact["downstream_count"] == 2
    assert set(bottleneck_impact["nodes_disconnected_if_removed"]) == {n_secret1.id, n_secret2.id}
    assert bottleneck_impact["disconnection_impact_score"] == 2

    # Run find_critical_node
    res = find_critical_node(scan.id, db)
    assert res["critical_node_id"] == n_bottleneck.id
    assert res["disconnection_impact_score"] == 2
    assert res["tie_existed"] is False

    # Check database state for is_critical flags
    nb_db = db.query(Node).filter(Node.id == n_bottleneck.id).first()
    ns1_db = db.query(Node).filter(Node.id == n_secret1.id).first()
    assert nb_db.is_critical is True
    assert ns1_db.is_critical is False
    db.close()


def test_tie_breaking_by_created_at():
    """
    Tie-breaking test with two nodes of equal impact score (score = 1 each).
    Confirms the earlier-created node wins and the tie is noted in the response.
    """
    db = TestingSessionLocal()
    scan = Scan(target_url="http://localhost:3000", status="COMPLETED")
    db.add(scan)
    db.commit()

    t1 = datetime.utcnow() - timedelta(hours=2)
    t2 = datetime.utcnow() - timedelta(hours=1)

    node_a = Node(scan_id=scan.id, label="Node A", node_type="endpoint", created_at=t1)
    node_a_sub = Node(scan_id=scan.id, label="Sub A", node_type="secret", created_at=t1)

    node_b = Node(scan_id=scan.id, label="Node B", node_type="endpoint", created_at=t2)
    node_b_sub = Node(scan_id=scan.id, label="Sub B", node_type="secret", created_at=t2)

    db.add_all([node_a, node_a_sub, node_b, node_b_sub])
    db.commit()

    e_a = Edge(scan_id=scan.id, source_node_id=node_a.id, target_node_id=node_a_sub.id, relation_type="LEADS_TO")
    e_b = Edge(scan_id=scan.id, source_node_id=node_b.id, target_node_id=node_b_sub.id, relation_type="LEADS_TO")
    db.add_all([e_a, e_b])
    db.commit()

    res = find_critical_node(scan.id, db)
    assert res["tie_existed"] is True
    assert res["tie_break_reason"] is not None
    assert "Tie detected: 2 nodes" in res["tie_break_reason"]
    assert res["critical_node_id"] == node_a.id

    # Verify DB flags
    na_db = db.query(Node).filter(Node.id == node_a.id).first()
    nb_db = db.query(Node).filter(Node.id == node_b.id).first()
    assert na_db.is_critical is True
    assert nb_db.is_critical is False
    db.close()


def test_idempotency_and_winner_movement():
    """
    Idempotency test: runs analysis twice with different graph states in between.
    Confirms is_critical correctly moves to the new winner and is unset from the old one.
    """
    db = TestingSessionLocal()
    scan = Scan(target_url="http://localhost:3000", status="COMPLETED")
    db.add(scan)
    db.commit()

    nA = Node(scan_id=scan.id, label="Node A", node_type="endpoint")
    nA_child = Node(scan_id=scan.id, label="Child A", node_type="secret")
    nB = Node(scan_id=scan.id, label="Node B", node_type="endpoint")
    db.add_all([nA, nA_child, nB])
    db.commit()

    eA = Edge(scan_id=scan.id, source_node_id=nA.id, target_node_id=nA_child.id, relation_type="LEADS_TO")
    db.add(eA)
    db.commit()

    # First run: Node A has impact score 1, Node B has impact score 0
    res1 = find_critical_node(scan.id, db)
    assert res1["critical_node_id"] == nA.id

    nA_db = db.query(Node).filter(Node.id == nA.id).first()
    nB_db = db.query(Node).filter(Node.id == nB.id).first()
    assert nA_db.is_critical is True
    assert nB_db.is_critical is False

    # Evolve graph state: add 2 children to Node B so Node B now has impact score 2
    nB_child1 = Node(scan_id=scan.id, label="Child B1", node_type="secret")
    nB_child2 = Node(scan_id=scan.id, label="Child B2", node_type="secret")
    db.add_all([nB_child1, nB_child2])
    db.commit()

    eB1 = Edge(scan_id=scan.id, source_node_id=nB.id, target_node_id=nB_child1.id, relation_type="LEADS_TO")
    eB2 = Edge(scan_id=scan.id, source_node_id=nB.id, target_node_id=nB_child2.id, relation_type="LEADS_TO")
    db.add_all([eB1, eB2])
    db.commit()

    # Second run: Node B should now win
    res2 = find_critical_node(scan.id, db)
    assert res2["critical_node_id"] == nB.id
    assert res2["disconnection_impact_score"] == 2

    # Verify is_critical moved in DB
    nA_db2 = db.query(Node).filter(Node.id == nA.id).first()
    nB_db2 = db.query(Node).filter(Node.id == nB.id).first()
    assert nA_db2.is_critical is False
    assert nB_db2.is_critical is True
    db.close()


def test_api_critical_node_routes():
    """
    Integration test for POST /scans/{scan_id}/critical-node-analysis and GET /scans/{scan_id}/critical-node.
    """
    db = TestingSessionLocal()
    scan = Scan(target_url="http://localhost:3000", status="COMPLETED")
    db.add(scan)
    db.commit()

    n_root = Node(scan_id=scan.id, label="API Gateway", node_type="service")
    n_target = Node(scan_id=scan.id, label="Admin Secret", node_type="secret")
    db.add_all([n_root, n_target])
    db.commit()

    edge = Edge(scan_id=scan.id, source_node_id=n_root.id, target_node_id=n_target.id, relation_type="EXPOSES")
    db.add(edge)
    db.commit()

    scan_id = scan.id
    root_id = n_root.id
    db.close()

    # 1. GET read-only endpoint before analysis
    resp_get_before = client.get(f"/scans/{scan_id}/critical-node")
    assert resp_get_before.status_code == 200
    assert resp_get_before.json()["critical_node"] is None

    # 2. POST run analysis
    resp_post = client.post(f"/scans/{scan_id}/critical-node-analysis")
    assert resp_post.status_code == 200
    data_post = resp_post.json()
    assert data_post["scan_id"] == scan_id
    assert data_post["critical_node_id"] == root_id
    assert data_post["critical_node"]["id"] == root_id
    assert data_post["critical_node"]["is_critical"] is True
    assert len(data_post["ranked_nodes"]) == 2

    # 3. GET read-only endpoint after analysis
    resp_get_after = client.get(f"/scans/{scan_id}/critical-node")
    assert resp_get_after.status_code == 200
    data_get = resp_get_after.json()
    assert data_get["scan_id"] == scan_id
    assert data_get["critical_node"] is not None
    assert data_get["critical_node"]["id"] == root_id
    assert data_get["critical_node"]["is_critical"] is True
