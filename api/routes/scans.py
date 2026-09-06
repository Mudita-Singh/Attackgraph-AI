from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from db.database import get_db
from db.models import Scan
from api.schemas import ScanCreate, ScanResponse, NmapScanResponse
from api.allowlist import allowlist_validator
from tools.nmap import execute_nmap_scan

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
