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
from tools.access_control_check import (
    _compare_responses,
    execute_access_control_check,
    find_path_identifier,
    _swap_path_identifier,
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


def test_compare_responses_differing_data():
    req = httpx.Request("GET", "http://localhost:3000/api/users?id=1")
    resp_a = httpx.Response(200, text='{"id": 1, "username": "alice", "email": "alice@example.com"}', request=req)
    resp_b = httpx.Response(200, text='{"id": 2, "username": "bob", "email": "bob@example.com"}', request=req)

    result = _compare_responses(resp_a, resp_b)
    assert result["is_potential_issue"] is True
    assert result["confidence"] == 0.6
    assert "different" in result["reasoning"]


def test_compare_responses_error_404():
    req = httpx.Request("GET", "http://localhost:3000/api/users?id=1")
    resp_a = httpx.Response(200, text='{"id": 1, "username": "alice"}', request=req)
    resp_b = httpx.Response(404, text='{"error": "User not found"}', request=req)

    result = _compare_responses(resp_a, resp_b)
    assert result["is_potential_issue"] is False
    assert result["confidence"] == 0.0
    assert "did not succeed" in result["reasoning"]


def test_compare_responses_generic_error_in_200():
    req = httpx.Request("GET", "http://localhost:3000/api/users?id=1")
    resp_a = httpx.Response(200, text='{"id": 1, "username": "alice"}', request=req)
    resp_b = httpx.Response(200, text='{"status": "error", "message": "User does not exist"}', request=req)

    result = _compare_responses(resp_a, resp_b)
    assert result["is_potential_issue"] is False
    assert result["confidence"] == 0.0
    assert "generic error/not-found page" in result["reasoning"]


def test_compare_responses_identical():
    req = httpx.Request("GET", "http://localhost:3000/api/users?id=1")
    resp_a = httpx.Response(200, text='{"id": 1, "username": "alice"}', request=req)
    resp_b = httpx.Response(200, text='{"id": 1, "username": "alice"}', request=req)

    result = _compare_responses(resp_a, resp_b)
    assert result["is_potential_issue"] is False
    assert result["confidence"] == 0.0
    assert "identical content" in result["reasoning"]


@patch("tools.access_control_check.httpx.Client")
def test_execute_access_control_check_flow(mock_httpx_client):
    db = TestingSessionLocal()
    scan = Scan(target_url="http://localhost:3000", status="INITIALIZED")
    db.add(scan)
    db.commit()

    node = Node(
        scan_id=scan.id,
        label="Endpoint ?id=1",
        node_type="endpoint",
        properties={"url": "http://localhost:3000/api/items?id=1"}
    )
    db.add(node)
    db.commit()

    mock_client_instance = MagicMock()
    mock_httpx_client.return_value.__enter__.return_value = mock_client_instance

    req = httpx.Request("GET", "http://localhost:3000/api/items?id=1")
    mock_client_instance.get.side_effect = [
        httpx.Response(200, text='{"item_id": 1, "name": "Secret Document A"}', request=req),
        httpx.Response(200, text='{"item_id": 2, "name": "Secret Document B"}', request=req),
    ]

    res = execute_access_control_check(scan.id, node.id, db)
    assert res["finding"]["is_potential_issue"] is True
    assert res["node"] is not None
    assert res["node"].node_type == "access_control_finding"
    assert res["edge"] is not None
    assert res["edge"].relation_type == "possible_access_control_issue"
    assert res["evidence"] is not None


def test_access_control_check_cross_scan_scoping():
    scan_a_id = client.post("/scans", json={"target_url": "http://localhost:3000"}).json()["id"]
    scan_b_id = client.post("/scans", json={"target_url": "http://localhost:8080"}).json()["id"]

    ffuf_nodes = client.post(f"/scans/{scan_b_id}/ffuf").json()["nodes"]
    node_b_id = ffuf_nodes[0]["id"]

    response = client.post(f"/scans/{scan_a_id}/nodes/{node_b_id}/access-control-check")
    assert response.status_code == 403
    assert "Security Violation" in response.json()["detail"]


def test_path_identifier_detection_and_swapping():
    url = "http://localhost:3000/rest/basket/1"
    path_id = find_path_identifier(url)
    assert path_id == (2, "1")

    swapped_url = _swap_path_identifier(url, path_id[0], "2")
    assert swapped_url == "http://localhost:3000/rest/basket/2"


def test_execute_access_control_check_non_parameterized_raises():
    db = TestingSessionLocal()
    scan = Scan(target_url="http://localhost:3000", status="INITIALIZED")
    db.add(scan)
    db.commit()

    node = Node(
        scan_id=scan.id,
        label="Static Endpoint",
        node_type="endpoint",
        properties={"url": "http://localhost:3000/rest/user/whoami"}
    )
    db.add(node)
    db.commit()

    with pytest.raises(ValueError) as exc_info:
        execute_access_control_check(scan.id, node.id, db)
    assert "neither query param nor numeric path segment" in str(exc_info.value)


@patch("tools.access_control_check.httpx.Client")
def test_execute_access_control_check_with_auth_token(mock_httpx_client):
    db = TestingSessionLocal()
    scan = Scan(target_url="http://localhost:3000", status="INITIALIZED")
    db.add(scan)
    db.commit()

    node = Node(
        scan_id=scan.id,
        label="Endpoint /rest/basket/1",
        node_type="endpoint",
        properties={"url": "http://localhost:3000/rest/basket/1"}
    )
    db.add(node)
    db.commit()

    mock_client_instance = MagicMock()
    mock_httpx_client.return_value.__enter__.return_value = mock_client_instance

    req = httpx.Request("GET", "http://localhost:3000/rest/basket/1")
    mock_client_instance.get.side_effect = [
        httpx.Response(200, text='{"id": 1, "items": []}', request=req),
        httpx.Response(200, text='{"id": 2, "items": [{"id": 99}]}', request=req),
    ]

    res = execute_access_control_check(scan.id, node.id, db, auth_token="my-test-jwt-token")
    assert res["finding"]["is_potential_issue"] is True
    assert mock_httpx_client.call_args.kwargs["headers"]["Authorization"] == "Bearer my-test-jwt-token"








