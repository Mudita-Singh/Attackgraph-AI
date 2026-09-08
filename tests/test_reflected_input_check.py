import pytest
from unittest.mock import patch, MagicMock
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.database import Base, get_db
from db.models import Scan, Node
from api.main import app
from fastapi.testclient import TestClient
from tools.reflected_input_check import (
    _generate_marker,
    _find_query_param,
    _build_marked_url,
    _classify_reflection,
    execute_reflected_input_check,
)

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


def test_classify_reflection_plain_text():
    marker = "AGTEST1234567890AB"
    body = f"<html><body>Result for {marker}</body></html>"
    res = _classify_reflection(body, marker)
    assert res["reflected"] is True
    assert res["context"] == "plain_text_or_unknown"
    assert res["encoded"] is False


def test_classify_reflection_script_tag():
    marker = "AGTEST1234567890AB"
    body = f"<html><script>var q = '{marker}';</script></html>"
    res = _classify_reflection(body, marker)
    assert res["reflected"] is True
    assert res["context"] == "script_tag"
    assert res["encoded"] is False


def test_classify_reflection_html_attribute():
    marker = "AGTEST1234567890AB"
    body = f'<html><input type="text" value="{marker}"></html>'
    res = _classify_reflection(body, marker)
    assert res["reflected"] is True
    assert res["context"] == "html_attribute"
    assert res["encoded"] is False


def test_classify_reflection_encoded():
    marker = "<AGTEST123456>"
    body = f"<div>Search for &lt;AGTEST123456> and raw {marker}</div>"
    res = _classify_reflection(body, marker)
    assert res["reflected"] is True
    assert res["encoded"] is True



def test_classify_reflection_not_reflected():
    marker = "AGTEST1234567890AB"
    body = "<html><body>No reflection here</body></html>"
    res = _classify_reflection(body, marker)
    assert res["reflected"] is False
    assert res["context"] is None
    assert res["encoded"] is None


@patch("tools.reflected_input_check.httpx.Client")
def test_execute_reflected_input_check_unencoded_plain_text(mock_httpx_client):
    db = TestingSessionLocal()
    scan = Scan(target_url="http://localhost:3000", status="INITIALIZED")
    db.add(scan)
    db.commit()

    node = Node(
        scan_id=scan.id,
        label="Endpoint ?q=test",
        node_type="endpoint",
        properties={"url": "http://localhost:3000/search?q=test"}
    )
    db.add(node)
    db.commit()

    mock_client_instance = MagicMock()
    mock_httpx_client.return_value.__enter__.return_value = mock_client_instance

    def mock_get(url):
        # Extract marker from query param in request URL
        param_val = url.split("q=")[-1]
        return httpx.Response(200, text=f"Search results for: {param_val}")

    mock_client_instance.get.side_effect = mock_get

    res = execute_reflected_input_check(scan.id, node.id, db)
    assert res["classification"]["reflected"] is True
    assert res["classification"]["encoded"] is False
    assert res["classification"]["context"] == "plain_text_or_unknown"
    assert res["node"] is not None
    assert res["node"].node_type == "reflected_input_finding"
    assert res["edge"] is not None
    assert res["edge"].confidence == 0.55
    assert res["edge"].pattern_key == "reflected_input:unencoded_html_context"
    assert res["evidence"] is not None


@patch("tools.reflected_input_check._generate_marker")
@patch("tools.reflected_input_check.httpx.Client")
def test_execute_reflected_input_check_encoded(mock_httpx_client, mock_gen_marker):
    mock_gen_marker.return_value = "<AGTEST123456>"

    db = TestingSessionLocal()
    scan = Scan(target_url="http://localhost:3000", status="INITIALIZED")
    db.add(scan)
    db.commit()

    node = Node(
        scan_id=scan.id,
        label="Endpoint ?q=test",
        node_type="endpoint",
        properties={"url": "http://localhost:3000/search?q=test"}
    )
    db.add(node)
    db.commit()

    mock_client_instance = MagicMock()
    mock_httpx_client.return_value.__enter__.return_value = mock_client_instance

    # Response includes both raw marker and encoded variant
    mock_client_instance.get.return_value = httpx.Response(
        200, text="<div>Result &lt;AGTEST123456> and <AGTEST123456></div>"
    )

    res = execute_reflected_input_check(scan.id, node.id, db)
    assert res["classification"]["reflected"] is True
    assert res["classification"]["encoded"] is True
    assert res["node"] is not None
    assert res["edge"] is not None
    assert res["edge"].confidence == 0.3
    assert res["edge"].pattern_key == "reflected_input:encoded_context"


@patch("tools.reflected_input_check.httpx.Client")
def test_execute_reflected_input_check_not_reflected(mock_httpx_client):
    db = TestingSessionLocal()
    scan = Scan(target_url="http://localhost:3000", status="INITIALIZED")
    db.add(scan)
    db.commit()

    node = Node(
        scan_id=scan.id,
        label="Endpoint ?q=test",
        node_type="endpoint",
        properties={"url": "http://localhost:3000/search?q=test"}
    )
    db.add(node)
    db.commit()

    mock_client_instance = MagicMock()
    mock_httpx_client.return_value.__enter__.return_value = mock_client_instance
    mock_client_instance.get.return_value = httpx.Response(200, text="Search results: static output")

    res = execute_reflected_input_check(scan.id, node.id, db)
    assert res["classification"]["reflected"] is False
    assert res["node"] is None
    assert res["edge"] is None
    assert res["evidence"] is not None


def test_reflected_input_check_cross_scan_scoping():
    scan_a_resp = client.post("/scans", json={"target_url": "http://localhost:3000"})
    assert scan_a_resp.status_code == 201
    scan_a_id = scan_a_resp.json()["id"]

    scan_b_resp = client.post("/scans", json={"target_url": "http://localhost:8080"})
    assert scan_b_resp.status_code == 201
    scan_b_id = scan_b_resp.json()["id"]

    ffuf_nodes = client.post(f"/scans/{scan_b_id}/ffuf").json()["nodes"]
    node_b_id = ffuf_nodes[0]["id"]

    response = client.post(f"/scans/{scan_a_id}/nodes/{node_b_id}/reflected-input-check")
    assert response.status_code == 403
    assert "Security Violation" in response.json()["detail"]




def test_execute_reflected_input_check_no_query_param_raises():
    db = TestingSessionLocal()
    scan = Scan(target_url="http://localhost:3000", status="INITIALIZED")
    db.add(scan)
    db.commit()

    node = Node(
        scan_id=scan.id,
        label="Static Endpoint",
        node_type="endpoint",
        properties={"url": "http://localhost:3000/static/page"}
    )
    db.add(node)
    db.commit()

    with pytest.raises(ValueError) as exc_info:
        execute_reflected_input_check(scan.id, node.id, db)
    assert "has no query parameter" in str(exc_info.value)
