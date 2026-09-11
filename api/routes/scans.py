from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import Scan
from api.schemas import (
    ScanCreate, ScanResponse, NmapScanResponse, FfufScanResponse,
    HttpProbeRequest, HttpProbeResponse, AccessControlCheckRequest, AccessControlCheckResponse,
    ReflectedInputCheckResponse, AgentRunResponse, AgentRunRequest
)

from api.allowlist import allowlist_validator
from tools.nmap import execute_nmap_scan
from tools.ffuf import execute_ffuf_scan
from tools.http_probe import execute_http_probe
from tools.access_control_check import execute_access_control_check
from tools.reflected_input_check import execute_reflected_input_check
from agent.loop import run_agent_loop



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








