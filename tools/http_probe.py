import httpx
from datetime import datetime
from urllib.parse import urlparse
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from db.models import Scan, Node, Evidence, Edge
from tools.envelope import ToolOutputEnvelope
from tools.secret_detection import extract_secrets_from_text

def execute_http_probe(
    scan_id: str,
    node_id: str,
    db: Session,
    method: str = "GET",
    body: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes a targeted HTTP probe against a specific discovered node.
    1. Looks up scan record by scan_id.
    2. Looks up node record by node_id.
    3. Validates node ownership: node.scan_id MUST equal scan_id.
    4. Builds target URL from scan's target_url + node's path/endpoint property.
    5. Sends real HTTP request via httpx.
    6. Wraps response in ToolOutputEnvelope.
    7. Stores Evidence row linked to scan_id AND node_id.
    8. Scans response body for secrets and creates potential_secret Nodes + exposes_secret Edges.
    Fails loudly on errors or scope violation. Never fakes responses.
    """
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise ValueError(f"Scan with ID '{scan_id}' not found")

    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise ValueError(f"Node with ID '{node_id}' not found")

    # Scope Enforcement: Node MUST belong to THIS scan_id
    if node.scan_id != scan.id:
        raise ValueError(
            f"Security Violation: Node '{node_id}' does not belong to scan_id '{scan_id}'."
        )

    base_url = scan.target_url.rstrip('/')
    endpoint_path = node.properties.get("path", "") if node.properties else ""

    if endpoint_path:
        formatted_path = f"/{endpoint_path.lstrip('/')}"
        target_full_url = f"{base_url}{formatted_path}"
    else:
        target_full_url = base_url

    req_method = method.upper() if method else "GET"

    try:
        with httpx.Client(timeout=10.0, follow_redirects=False) as client:
            if req_method == "POST":
                resp = client.post(target_full_url, content=body or "")
            else:
                resp = client.get(target_full_url)

        status_code = resp.status_code
        headers_dict = dict(resp.headers)
        
        # Build raw HTTP response text (status line + headers + body safely decoded)
        headers_lines = [f"{k}: {v}" for k, v in headers_dict.items()]
        headers_text = "\n".join(headers_lines)
        try:
            body_text = resp.content.decode('utf-8', errors='ignore')
        except Exception:
            body_text = "<binary content>"

        raw_output = f"HTTP/{resp.http_version} {status_code} {resp.reason_phrase}\n{headers_text}\n\n{body_text}"
        raw_output = raw_output.replace('\x00', '')

        parsed_findings = {
            "status_code": status_code,
            "headers": headers_dict,
            "body_length": len(resp.content),
            "content_type": resp.headers.get("content-type", ""),
            "method": req_method,
            "url": target_full_url
        }

    except Exception as e:
        raise RuntimeError(f"HTTP Probe execution failed for '{target_full_url}': {str(e)}")

    envelope = ToolOutputEnvelope(
        tool="http_probe",
        target=target_full_url,
        raw_output=raw_output,
        parsed_findings=parsed_findings,
        timestamp=datetime.utcnow()
    )

    # Store Evidence row linked to scan_id AND node_id
    evidence = Evidence(
        scan_id=scan.id,
        node_id=node.id,
        tool_name=envelope.tool,
        raw_output=envelope.raw_output,
        parsed_findings=envelope.parsed_findings,
        timestamp=envelope.timestamp
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    # Phase 6: Secret Extraction on captured probe response body
    detected_secrets = extract_secrets_from_text(body_text)
    secret_nodes = []
    secret_edges = []

    for secret in detected_secrets:
        # Create secret node
        secret_node = Node(
            scan_id=scan.id,
            label=f"Secret: {secret['name']} ({secret['match_preview']})",
            node_type="potential_secret",
            is_critical=True,
            properties={
                "secret_type": secret["pattern_key"],
                "name": secret["name"],
                "match_preview": secret["match_preview"],
                "evidence_id": evidence.id
            }
        )
        db.add(secret_node)
        db.flush()

        # Create edge from probed endpoint node -> secret node
        edge = Edge(
            scan_id=scan.id,
            source_node_id=node.id,
            target_node_id=secret_node.id,
            relation_type="exposes_secret",
            pattern_key=secret["pattern_key"],
            confidence=secret["confidence"],
            status="verified",
            reasoning=f"Pattern '{secret['name']}' matched in response from '{target_full_url}': {secret['description']}",
            properties={
                "evidence_id": evidence.id,
                "match_preview": secret["match_preview"]
            }
        )
        db.add(edge)
        secret_nodes.append(secret_node)
        secret_edges.append(edge)

    if detected_secrets:
        db.commit()

    return {
        "scan_id": scan.id,
        "node_id": node.id,
        "evidence": evidence,
        "envelope": envelope,
        "detected_secrets": len(detected_secrets)
    }
