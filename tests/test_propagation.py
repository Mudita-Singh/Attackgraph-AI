import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.database import Base, get_db
from db.models import Scan, Node, Edge, HumanCorrection
from api.main import app
from graph.propagation import (
    find_downstream_nodes,
    recalculate_node_support,
    propagate_invalidation
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


def test_db_schema_undermined_column_exists():
    """
    Migration & DB check confirming the new 'undermined' column and default value exist in DB.
    """
    inspector = inspect(engine)
    columns = {col["name"]: col for col in inspector.get_columns("nodes")}
    assert "undermined" in columns
    assert columns["undermined"]["type"].__class__.__name__ == "BOOLEAN"


def test_propagation_section_13_3_multi_path_scenario():
    """
    Unit test matching Section 13.3's exact scenario:
    Path 1: Credential -> Admin -> Sensitive_Data (edges e1: Credential->Admin, e2: Admin->Sensitive_Data)
    Path 2: Other_Credential -> Admin -> Sensitive_Data (edge e3: Other_Credential->Admin)

    When edge e1 (Credential -> Admin) is invalidated:
    - Admin is still supported by Path 2 (Other_Credential -> Admin).
    - Sensitive_Data is still supported by Path 2 (Other_Credential -> Admin -> Sensitive_Data).
    Neither Admin nor Sensitive_Data should become undermined.
    """
    db = TestingSessionLocal()
    scan = Scan(target_url="http://localhost:3000", status="COMPLETED")
    db.add(scan)
    db.commit()

    n_cred1 = Node(scan_id=scan.id, label="Credential 1", node_type="credential")
    n_cred2 = Node(scan_id=scan.id, label="Other Credential", node_type="credential")
    n_admin = Node(scan_id=scan.id, label="Admin Role", node_type="role")
    n_data = Node(scan_id=scan.id, label="Sensitive Data", node_type="asset")
    db.add_all([n_cred1, n_cred2, n_admin, n_data])
    db.commit()

    e1 = Edge(scan_id=scan.id, source_node_id=n_cred1.id, target_node_id=n_admin.id, relation_type="GRANTS", status="human_invalidated", verification_outcome="HUMAN_INVALIDATED")
    e2 = Edge(scan_id=scan.id, source_node_id=n_admin.id, target_node_id=n_data.id, relation_type="ACCESSES", status="verified", verification_outcome="VERIFIED")
    e3 = Edge(scan_id=scan.id, source_node_id=n_cred2.id, target_node_id=n_admin.id, relation_type="GRANTS", status="verified", verification_outcome="VERIFIED")
    db.add_all([e1, e2, e3])
    db.commit()

    scan_id, e1_id = scan.id, e1.id
    admin_id, data_id = n_admin.id, n_data.id

    res = propagate_invalidation(e1_id, scan_id, db)

    assert res["invalidated_edge_id"] == e1_id
    assert admin_id in res["still_supported_nodes"]
    assert data_id in res["still_supported_nodes"]
    assert len(res["undermined_nodes"]) == 0

    # Confirm nodes in DB are NOT undermined
    n_admin_db = db.query(Node).filter(Node.id == admin_id).first()
    n_data_db = db.query(Node).filter(Node.id == data_id).first()
    assert n_admin_db.undermined is False
    assert n_data_db.undermined is False
    db.close()


def test_propagation_single_path_becomes_undermined():
    """
    Unit test where a node has only ONE path in, gets invalidated, and correctly becomes undermined.
    Graph: Service -> Endpoint -> Secrets
    Invalidate Service -> Endpoint.
    Both Endpoint and Secrets MUST become undermined (undermined=True).
    """
    db = TestingSessionLocal()
    scan = Scan(target_url="http://localhost:3000", status="COMPLETED")
    db.add(scan)
    db.commit()

    n_svc = Node(scan_id=scan.id, label="Service 3000", node_type="service")
    n_ep = Node(scan_id=scan.id, label="Endpoint /api/secret", node_type="endpoint")
    n_sec = Node(scan_id=scan.id, label="AWS Key Secret", node_type="secret")
    db.add_all([n_svc, n_ep, n_sec])
    db.commit()

    e1 = Edge(scan_id=scan.id, source_node_id=n_svc.id, target_node_id=n_ep.id, relation_type="EXPOSES", status="human_invalidated", verification_outcome="HUMAN_INVALIDATED")
    e2 = Edge(scan_id=scan.id, source_node_id=n_ep.id, target_node_id=n_sec.id, relation_type="CONTAINS", status="unverified")
    db.add_all([e1, e2])
    db.commit()

    scan_id, e1_id = scan.id, e1.id
    ep_id, sec_id = n_ep.id, n_sec.id

    res = propagate_invalidation(e1_id, scan_id, db)

    assert ep_id in res["undermined_nodes"]
    assert sec_id in res["undermined_nodes"]
    assert len(res["still_supported_nodes"]) == 0

    # Verify nodes in DB are marked undermined=True
    n_ep_db = db.query(Node).filter(Node.id == ep_id).first()
    n_sec_db = db.query(Node).filter(Node.id == sec_id).first()
    assert n_ep_db.undermined is True
    assert n_sec_db.undermined is True
    assert "Path unsupported after invalidation" in n_ep_db.properties["undermined_reason"]
    assert "Path unsupported after invalidation" in n_sec_db.properties["undermined_reason"]

    # Verify HumanCorrection propagation event row created
    corr = db.query(HumanCorrection).filter(HumanCorrection.correction_type == "PROPAGATION").first()
    assert corr is not None
    assert corr.target_id == e1_id
    assert "2 node(s) undermined" in corr.notes
    db.close()


def test_api_human_review_refute_triggers_propagation():
    """
    Integration test confirming POST /scans/{scan_id}/edges/{edge_id}/human-review with decision="refute"
    automatically triggers propagation and returns propagation_result in JSON response.
    """
    db = TestingSessionLocal()
    scan = Scan(target_url="http://localhost:3000", status="COMPLETED")
    db.add(scan)
    db.commit()

    n1 = Node(scan_id=scan.id, label="Root Service", node_type="service")
    n2 = Node(scan_id=scan.id, label="Target Finding Node", node_type="finding")
    db.add_all([n1, n2])
    db.commit()

    edge = Edge(scan_id=scan.id, source_node_id=n1.id, target_node_id=n2.id, relation_type="LEADS_TO", status="unverified", pattern_key="access_control_check")
    db.add(edge)
    db.commit()

    scan_id, edge_id, n2_id = scan.id, edge.id, n2.id
    db.close()

    response = client.post(
        f"/scans/{scan_id}/edges/{edge_id}/human-review",
        json={"decision": "refute", "reviewer": "auditor_1", "reason": "Incorrect relation"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "refute"
    assert data["new_status"] == "human_invalidated"
    assert data["propagation_result"] is not None

    prop = data["propagation_result"]
    assert prop["invalidated_edge_id"] == edge_id
    assert n2_id in prop["undermined_nodes"]

    # Verify DB node updated to undermined=True
    db2 = TestingSessionLocal()
    n2_db = db2.query(Node).filter(Node.id == n2_id).first()
    assert n2_db.undermined is True
    db2.close()
