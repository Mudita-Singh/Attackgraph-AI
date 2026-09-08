"""
tools/access_control_check.py

Implements Section 6.5 of the project spec: a conservative, evidence-based
comparison utility that tests whether changing an identifier in an
authenticated request reveals another user's data (a potential IDOR /
broken-access-control pattern).

This module only operates against targets already tied to an existing Scan
record created through the Phase 2 allowlist-enforced /scans endpoint. It
never validates a raw URL independently and never modifies data (GET only).
"""

import re
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlparse, urlencode, parse_qs, urlunparse

import httpx
from sqlalchemy.orm import Session

from db.models import Scan, Node, Edge, Evidence
from tools.envelope import ToolOutputEnvelope

IDENTIFIER_PARAM_PATTERN = re.compile(r"^[A-Za-z_]*id$", re.IGNORECASE)


def find_identifier_param(url: str) -> Optional[Tuple[str, str]]:
    """Find a query parameter that looks like an identifier, e.g. ?id=123."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    for key, values in params.items():
        if IDENTIFIER_PARAM_PATTERN.match(key) and values:
            return key, values[0]
    return None


def _swap_identifier(url: str, param_name: str, new_value: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    params[param_name] = [new_value]
    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


PATH_IDENTIFIER_PATTERN = re.compile(r"^\d+$")


def find_path_identifier(url: str) -> Optional[Tuple[int, str]]:
    """
    Finds a purely-numeric path segment that looks like a resource
    identifier, e.g. /rest/basket/1 -> segment index 2, value "1".
    Returns (segment_index, value) or None.
    """
    parsed = urlparse(url)
    segments = [s for s in parsed.path.split("/") if s]
    for i, seg in enumerate(segments):
        if PATH_IDENTIFIER_PATTERN.match(seg):
            return i, seg
    return None


def _swap_path_identifier(url: str, segment_index: int, new_value: str) -> str:
    parsed = urlparse(url)
    segments = [s for s in parsed.path.split("/") if s]
    segments[segment_index] = new_value
    new_path = "/" + "/".join(segments)
    return urlunparse(parsed._replace(path=new_path))



def _increment_identifier(value: str) -> Optional[str]:
    """Only handles numeric identifiers conservatively - no guessing otherwise."""
    if value.isdigit():
        return str(int(value) + 1)
    return None


def execute_access_control_check(
    scan_id: str,
    node_id: str,
    db: Session,
    session_cookies: Optional[Dict[str, str]] = None,
    auth_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sends two GET requests using the SAME session/cookies/auth_token:
      Request A: the endpoint's original identifier value.
      Request B: the same endpoint with the identifier changed.

    Only flags a finding if both requests succeeded (2xx), the bodies are
    meaningfully different, and response B doesn't look like a generic
    error/not-found page. Records an observation with both requests as
    evidence for human review - never asserts a confirmed vulnerability.
    """
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise ValueError(f"Scan with ID '{scan_id}' not found")

    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise ValueError(f"Node with ID '{node_id}' not found")

    if node.scan_id != scan.id:
        raise ValueError(f"Security Violation: Node '{node_id}' does not belong to scan_id '{scan_id}'.")

    endpoint_url = (node.properties or {}).get("url") or (node.properties or {}).get("path")
    if not endpoint_url:
        raise ValueError(f"Node '{node_id}' has no probeable URL in its properties")

    if endpoint_url.startswith("/"):
        endpoint_url = scan.target_url.rstrip("/") + endpoint_url

    id_param = find_identifier_param(endpoint_url)
    path_id = None if id_param else find_path_identifier(endpoint_url)

    if not id_param and not path_id:
        raise ValueError(
            f"Node '{node_id}' endpoint '{endpoint_url}' has no identifier "
            f"(neither query param nor numeric path segment) - not applicable"
        )

    if id_param:
        param_name, original_value = id_param
        new_value = _increment_identifier(original_value)
        if new_value is None:
            raise ValueError(f"Identifier '{original_value}' is not numeric, skipping")
        url_b = _swap_identifier(endpoint_url, param_name, new_value)
    else:
        segment_index, original_value = path_id
        new_value = _increment_identifier(original_value)
        if new_value is None:
            raise ValueError(f"Path identifier '{original_value}' is not numeric, skipping")
        url_b = _swap_path_identifier(endpoint_url, segment_index, new_value)
        param_name = f"path_segment_{segment_index}"

    headers = {}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

    with httpx.Client(
        cookies=session_cookies or {},
        headers=headers,
        timeout=10.0,
        follow_redirects=True,
    ) as client:
        resp_a = client.get(endpoint_url)
        resp_b = client.get(url_b)


    finding = _compare_responses(resp_a, resp_b)

    envelope = ToolOutputEnvelope(
        tool="access_control_check",
        target=endpoint_url,
        raw_output=(
            f"REQUEST A: GET {endpoint_url}\n"
            f"STATUS A: {resp_a.status_code}\nBODY A (first 500 chars):\n{resp_a.text[:500]}\n\n"
            f"REQUEST B: GET {url_b}\n"
            f"STATUS B: {resp_b.status_code}\nBODY B (first 500 chars):\n{resp_b.text[:500]}"
        ),
        parsed_findings={
            "request_a": {"url": endpoint_url, "status_code": resp_a.status_code, "body_length": len(resp_a.content)},
            "request_b": {"url": url_b, "status_code": resp_b.status_code, "body_length": len(resp_b.content)},
            "identifier_param": param_name,
            "original_value": original_value,
            "tested_value": new_value,
            "finding": finding,
        },
        timestamp=datetime.utcnow(),
    )

    evidence = Evidence(
        scan_id=scan.id,
        node_id=node.id,
        tool_name=envelope.tool,
        raw_output=envelope.raw_output,
        parsed_findings=envelope.parsed_findings,
        timestamp=envelope.timestamp,
    )
    db.add(evidence)
    db.flush()

    result = {"scan_id": scan.id, "evidence": evidence, "finding": finding, "node": None, "edge": None}

    if finding["is_potential_issue"]:
        new_node = Node(
            scan_id=scan.id,
            label=f"Possible Access Control Issue: {param_name}={new_value} on {urlparse(endpoint_url).path}",
            node_type="access_control_finding",
            is_critical=False,
            properties={
                "endpoint": endpoint_url,
                "param": param_name,
                "original_value": original_value,
                "tested_value": new_value,
                "evidence_id": evidence.id,
            },
        )
        db.add(new_node)
        db.flush()

        edge = Edge(
            scan_id=scan.id,
            source_node_id=node.id,
            target_node_id=new_node.id,
            relation_type="possible_access_control_issue",
            confidence=finding["confidence"],
            status="unverified",
            reasoning=finding["reasoning"],
            pattern_key="access_control_check:same_session_different_identifier",
        )
        db.add(edge)
        db.flush()

        result["node"] = new_node
        result["edge"] = edge

    scan.status = "ACCESS_CONTROL_CHECK_COMPLETED"
    db.commit()
    db.refresh(evidence)
    return result


def _compare_responses(resp_a: httpx.Response, resp_b: httpx.Response) -> Dict[str, Any]:
    """
    Conservative comparison: only flags when both requests succeeded, the
    bodies are meaningfully different, and B doesn't look like a generic
    error page.
    """
    if resp_a.status_code // 100 != 2 or resp_b.status_code // 100 != 2:
        return {
            "is_potential_issue": False,
            "confidence": 0.0,
            "reasoning": f"Not flagged: one or both requests did not succeed "
                         f"(status A={resp_a.status_code}, status B={resp_b.status_code}).",
        }

    body_a = resp_a.text.strip()
    body_b = resp_b.text.strip()

    if body_a == body_b:
        return {
            "is_potential_issue": False,
            "confidence": 0.0,
            "reasoning": "Not flagged: both responses returned identical content.",
        }

    error_markers = ["not found", "error", "invalid", "does not exist", "unauthorized", "forbidden"]
    if any(m in body_b.lower() for m in error_markers) and len(body_b) < 500:
        return {
            "is_potential_issue": False,
            "confidence": 0.0,
            "reasoning": "Not flagged: response B looks like a generic error/not-found page.",
        }

    return {
        "is_potential_issue": True,
        "confidence": 0.6,
        "reasoning": (
            f"Same session used for both requests. Changing the identifier returned a "
            f"different ({len(body_b)}-byte vs {len(body_a)}-byte), non-error-looking "
            f"response. This is an observation for human review, not a confirmed "
            f"vulnerability - manual verification is required."
        ),
    }
