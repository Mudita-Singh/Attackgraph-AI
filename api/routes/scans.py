from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import Scan, Node, Edge, Evidence
from api.schemas import (
    ScanCreate, ScanResponse, NmapScanResponse, FfufScanResponse,
    HttpProbeRequest, HttpProbeResponse, AccessControlCheckRequest, AccessControlCheckResponse,
    ReflectedInputCheckResponse, AgentRunResponse, AgentRunRequest,
    EvidenceResponse, EvidenceSummary, GraphNodeResponse, GraphEdgeResponse, GraphResponse,
    PathConfidenceResponse
)

from api.allowlist import allowlist_validator
from tools.nmap import execute_nmap_scan
from tools.ffuf import execute_ffuf_scan
from tools.http_probe import execute_http_probe
from tools.access_control_check import execute_access_control_check
from tools.reflected_input_check import execute_reflected_input_check
from agent.loop import run_agent_loop
from graph.confidence import find_all_paths_to_node, calculate_path_confidence




router = APIRouter(prefix="/scans", tags=["scans"])

@router.post("", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
def create_scan(scan_in: ScanCreate, db: Session = Depends(get_db)):
    """
    POST /scans
    Hard security requirement: Validates target against server-side allowlist BEFORE any action.
    Rejects any target not on the allowlist with HTTP 403 Forbidden.
    """
    is_allowed = allowlist_validator.is_target_allowed(scan_in.target_url)
    
    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Security Violation: Target '{scan_in.target_url}' is not on the server-side target allowlist."
        )

    scan = Scan(
        target_url=scan_in.target_url,
        status="INITIALIZED"
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)
    return scan

@router.get("/{scan_id}", response_model=ScanResponse)
def get_scan(scan_id: str, db: Session = Depends(get_db)):
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return scan

@router.post("/{scan_id}/nmap", response_model=NmapScanResponse, status_code=status.HTTP_200_OK)
def trigger_nmap_scan(scan_id: str, db: Session = Depends(get_db)):
    """
    POST /scans/{scan_id}/nmap
    Executes Nmap scan against the stored target_url of an existing scan record.
    Returns created evidence and node references.
    """
    try:
        result = execute_nmap_scan(scan_id, db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/{scan_id}/ffuf", response_model=FfufScanResponse, status_code=status.HTTP_200_OK)
def trigger_ffuf_scan(scan_id: str, db: Session = Depends(get_db)):
    """
    POST /scans/{scan_id}/ffuf
    Executes ffuf endpoint scan against stored target_url of existing scan.
    Returns created evidence and endpoint node references.
    """
    try:
        result = execute_ffuf_scan(scan_id, db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/{scan_id}/nodes/{node_id}/probe", response_model=HttpProbeResponse, status_code=status.HTTP_200_OK)
def trigger_node_probe(
    scan_id: str,
    node_id: str,
    probe_in: Optional[HttpProbeRequest] = None,
    db: Session = Depends(get_db)
):
    """
    POST /scans/{scan_id}/nodes/{node_id}/probe
    Executes a targeted HTTP probe against a specific discovered node.
    Enforces cross-scan node scoping (node.scan_id MUST match scan_id).
    """
    method = probe_in.method if probe_in else "GET"
    body = probe_in.body if probe_in else None

    try:
        result = execute_http_probe(scan_id, node_id, db, method=method, body=body)
        return result
    except ValueError as e:
        if "Security Violation" in str(e):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{scan_id}/nodes/{node_id}/access-control-check", response_model=AccessControlCheckResponse, status_code=status.HTTP_200_OK)
def trigger_access_control_check(
    scan_id: str,
    node_id: str,
    check_in: Optional[AccessControlCheckRequest] = None,
    db: Session = Depends(get_db)
):
    """
    POST /scans/{scan_id}/nodes/{node_id}/access-control-check
    Executes access control check against a parameterized endpoint node.
    Enforces cross-scan node scoping (node.scan_id MUST match scan_id).
    """
    auth_token = check_in.auth_token if check_in else None
    session_cookies = check_in.session_cookies if check_in else None

    try:
        result = execute_access_control_check(
            scan_id, node_id, db, session_cookies=session_cookies, auth_token=auth_token
        )
        return result
    except ValueError as e:
        if "Security Violation" in str(e):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{scan_id}/nodes/{node_id}/reflected-input-check", response_model=ReflectedInputCheckResponse, status_code=status.HTTP_200_OK)
def trigger_reflected_input_check(
    scan_id: str,
    node_id: str,
    db: Session = Depends(get_db)
):
    """
    POST /scans/{scan_id}/nodes/{node_id}/reflected-input-check
    Executes reflected input check against a query-parameterized endpoint node.
    Enforces cross-scan node scoping (node.scan_id MUST match scan_id).
    """
    try:
        result = execute_reflected_input_check(scan_id, node_id, db)
        return result
    except ValueError as e:
        if "Security Violation" in str(e):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{scan_id}/agent/run", response_model=AgentRunResponse, status_code=status.HTTP_200_OK)
def trigger_agent_run(
    scan_id: str,
    run_in: Optional[AgentRunRequest] = None,
    max_steps: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    POST /scans/{scan_id}/agent/run
    Triggers the autonomous LLM function-calling agent decision loop for the scan.
    Accepts max_steps in JSON body or query parameter (defaults to 15).
    """
    steps_limit = max_steps if max_steps is not None else (run_in.max_steps if run_in and run_in.max_steps is not None else 15)

    try:
        result = run_agent_loop(scan_id, db, max_steps=steps_limit)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{scan_id}/graph", response_model=GraphResponse, status_code=status.HTTP_200_OK)
def get_scan_graph(scan_id: str, db: Session = Depends(get_db)):
    """
    GET /scans/{scan_id}/graph
    Returns full current graph for a scan: all nodes (with evidence summaries) and all edges.
    Enforces scan_id scoping. Returns 404 if scan not found.
    Returns empty nodes/edges lists (not an error) for a scan with nothing discovered yet.
    """
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")

    nodes = db.query(Node).filter(Node.scan_id == scan_id).all()
    edges = db.query(Edge).filter(Edge.scan_id == scan_id).all()

    node_responses = []
    for node in nodes:
        evidence_summaries = [
            EvidenceSummary(
                id=ev.id,
                tool_name=ev.tool_name,
                timestamp=ev.timestamp
            )
            for ev in node.evidence
        ]
        node_responses.append(
            GraphNodeResponse(
                id=node.id,
                label=node.label,
                node_type=node.node_type,
                is_critical=node.is_critical,
                properties=node.properties or {},
                evidence=evidence_summaries
            )
        )

    edge_responses = [
        GraphEdgeResponse(
            id=edge.id,
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            relation_type=edge.relation_type,
            confidence=edge.confidence,
            status=edge.status,
            reasoning=edge.reasoning,
            pattern_key=edge.pattern_key
        )
        for edge in edges
    ]

    return GraphResponse(
        scan_id=scan_id,
        nodes=node_responses,
        edges=edge_responses
    )


@router.get("/{scan_id}/nodes/{node_id}/evidence", response_model=List[EvidenceResponse], status_code=status.HTTP_200_OK)
def get_node_evidence(scan_id: str, node_id: str, db: Session = Depends(get_db)):
    """
    GET /scans/{scan_id}/nodes/{node_id}/evidence
    Returns FULL evidence details (raw_output, parsed_findings, timestamp, tool_name)
    for all evidence linked to a specific node.
    Enforces cross-scan node ownership scoping (HTTP 403 if node belongs to a different scan).
    """
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")

    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")

    if node.scan_id != scan_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Security Violation: Node '{node_id}' does not belong to scan_id '{scan_id}'."
        )

    evidence_list = db.query(Evidence).filter(Evidence.node_id == node_id).all()
    return evidence_list


@router.get("/{scan_id}/nodes/{node_id}/path-confidence", response_model=List[PathConfidenceResponse], status_code=status.HTTP_200_OK)
def get_node_path_confidence(scan_id: str, node_id: str, db: Session = Depends(get_db)):
    """
    GET /scans/{scan_id}/nodes/{node_id}/path-confidence
    Finds all paths from root nodes to node_id, computes weakest-link path confidence for each,
    and returns them sorted by path_confidence descending.
    Enforces cross-scan node scoping.
    """
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")

    node = db.query(Node).filter(Node.id == node_id).first()
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")

    if node.scan_id != scan_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Security Violation: Node '{node_id}' does not belong to scan_id '{scan_id}'."
        )

    paths = find_all_paths_to_node(node_id, scan_id, db)

    results = []
    for p in paths:
        if len(p) >= 2:
            path_info = calculate_path_confidence(p, db)
            results.append(path_info)
        elif len(p) == 1:
            results.append({
                "path": [node.label],
                "node_ids": [node.id],
                "edge_confidences": [],
                "path_confidence": 1.0,
                "weakest_edge": None
            })

    results.sort(key=lambda x: x["path_confidence"], reverse=True)
    return results










