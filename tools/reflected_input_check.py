"""
tools/reflected_input_check.py

Implements Section 6.6: a conservative check for reflected-input patterns.
Inserts a unique, harmless marker into a query parameter and checks whether
it comes back in the response body. Reflection alone is not proof of
anything exploitable - it's an observation for human review, same
conservative framing as the access-control check.
"""

import re
import secrets
from datetime import datetime
from typing import Optional, Dict, Any
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import httpx
from sqlalchemy.orm import Session

from db.models import Scan, Node, Edge, Evidence
from tools.envelope import ToolOutputEnvelope


def _generate_marker() -> str:
    """A unique, harmless, easily-searchable marker - not a payload."""
    return "AGTEST" + secrets.token_hex(6).upper()


def _find_query_param(url: str) -> Optional[str]:
    """Returns the first query parameter name found, or None."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    if params:
        return next(iter(params))
    return None


def _build_marked_url(url: str, param_name: str, marker: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    params[param_name] = [marker]
    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def _classify_reflection(body: str, marker: str) -> Dict[str, Any]:
    """
    Conservative classification of HOW the marker was reflected, not
    whether it's exploitable - that always requires human judgement.
    """
    if marker not in body:
        return {"reflected": False, "context": None, "encoded": None}

    idx = body.find(marker)
    surrounding = body[max(0, idx - 40): idx + len(marker) + 40]

    html_encoded_variants = [marker.replace("<", "&lt;"), marker.replace(">", "&gt;")]
    appears_encoded = any(v in body and v != marker for v in html_encoded_variants)

    in_script_tag = bool(re.search(r"<script[^>]*>[^<]*" + re.escape(marker), body, re.IGNORECASE))
    in_html_attribute = bool(re.search(r'=["\']?[^"\'>]*' + re.escape(marker), surrounding))
    in_plain_text = not in_script_tag and not in_html_attribute

    if in_script_tag:
        context = "script_tag"
    elif in_html_attribute:
        context = "html_attribute"
    else:
        context = "plain_text_or_unknown"

    return {
        "reflected": True,
        "context": context,
        "encoded": appears_encoded,
        "surrounding_snippet": surrounding,
    }


def execute_reflected_input_check(scan_id: str, node_id: str, db: Session) -> Dict[str, Any]:
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise ValueError(f"Scan with ID '{scan_id}' not found")

    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise ValueError(f"Node '{node_id}' not found")

    if node.scan_id != scan.id:
        raise ValueError(f"Security Violation: Node '{node_id}' does not belong to scan '{scan_id}'")

    endpoint_url = (node.properties or {}).get("url") or (node.properties or {}).get("path")
    if not endpoint_url:
        raise ValueError(f"Node '{node_id}' has no probeable URL in its properties")
    if endpoint_url.startswith("/"):
        endpoint_url = scan.target_url.rstrip("/") + endpoint_url

    param_name = _find_query_param(endpoint_url)
    if not param_name:
        raise ValueError(
            f"Node '{node_id}' endpoint '{endpoint_url}' has no query parameter "
            f"to test for reflection - not applicable for this check"
        )

    marker = _generate_marker()
    marked_url = _build_marked_url(endpoint_url, param_name, marker)

    with httpx.Client(timeout=10.0, follow_redirects=True) as client:
        resp = client.get(marked_url)

    classification = _classify_reflection(resp.text, marker)

    envelope = ToolOutputEnvelope(
        tool="reflected_input_check",
        target=marked_url,
        raw_output=(
            f"REQUEST: GET {marked_url}\n"
            f"STATUS: {resp.status_code}\n"
            f"MARKER: {marker}\n"
            f"REFLECTED: {classification['reflected']}\n"
            f"CONTEXT: {classification.get('context')}\n"
            f"BODY (first 500 chars):\n{resp.text[:500]}"
        ),
        parsed_findings={
            "param": param_name,
            "marker": marker,
            "status_code": resp.status_code,
            "classification": classification,
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

    result = {"scan_id": scan.id, "evidence": evidence, "classification": classification, "node": None, "edge": None}

    if classification["reflected"]:
        confidence = 0.3 if classification["encoded"] else 0.55

        new_node = Node(
            scan_id=scan.id,
            label=f"Reflected Input: {param_name} on {urlparse(endpoint_url).path}",
            node_type="reflected_input_finding",
            is_critical=False,
            properties={
                "endpoint": endpoint_url,
                "param": param_name,
                "context": classification["context"],
                "encoded": classification["encoded"],
                "evidence_id": evidence.id,
            },
        )
        db.add(new_node)
        db.flush()

        edge = Edge(
            scan_id=scan.id,
            source_node_id=node.id,
            target_node_id=new_node.id,
            relation_type="possible_reflected_input",
            confidence=confidence,
            status="unverified",
            reasoning=(
                f"A unique marker inserted into '{param_name}' was reflected back "
                f"in the response, in context '{classification['context']}', "
                f"{'HTML-encoded' if classification['encoded'] else 'NOT HTML-encoded'}. "
                f"Reflection alone does not confirm exploitability - this is an "
                f"observation for human review, not a confirmed vulnerability."
            ),
            pattern_key="reflected_input:unencoded_html_context" if not classification["encoded"] else "reflected_input:encoded_context",
        )
        db.add(edge)
        db.flush()

        result["node"] = new_node
        result["edge"] = edge

    scan.status = "REFLECTED_INPUT_CHECK_COMPLETED"
    db.commit()
    db.refresh(evidence)
    return result
