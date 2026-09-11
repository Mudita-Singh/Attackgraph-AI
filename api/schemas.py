from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, HttpUrl, ConfigDict

class ScanCreate(BaseModel):
    target_url: str

class ScanResponse(BaseModel):
    id: str
    target_url: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class NodeCreate(BaseModel):
    scan_id: str
    label: str
    node_type: str
    is_critical: bool = False
    properties: Dict[str, Any] = {}

class NodeResponse(BaseModel):
    id: str
    scan_id: str
    label: str
    node_type: str
    is_critical: bool
    properties: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class EdgeCreate(BaseModel):
    scan_id: str
    source_node_id: str
    target_node_id: str
    relation_type: str
    pattern_key: Optional[str] = None
    confidence: Optional[float] = None
    status: str = "unverified"
    verification_outcome: Optional[str] = None
    reasoning: Optional[str] = None
    step: Optional[int] = None
    properties: Dict[str, Any] = {}

class EdgeResponse(BaseModel):
    id: str
    scan_id: str
    source_node_id: str
    target_node_id: str
    relation_type: str
    pattern_key: Optional[str] = None
    confidence: Optional[float] = None
    status: str
    verification_outcome: Optional[str] = None
    reasoning: Optional[str] = None
    step: Optional[int] = None
    properties: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class EvidenceResponse(BaseModel):
    id: str
    scan_id: str
    node_id: Optional[str] = None
    edge_id: Optional[str] = None
    tool_name: str
    raw_output: Optional[str] = None
    parsed_findings: Dict[str, Any]
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

class NmapScanResponse(BaseModel):
    scan_id: str
    evidence: EvidenceResponse
    nodes: List[NodeResponse]

class FfufScanResponse(BaseModel):
    scan_id: str
    evidence: EvidenceResponse
    nodes: List[NodeResponse]

class HttpProbeRequest(BaseModel):
    method: str = "GET"
    body: Optional[str] = None

class HttpProbeResponse(BaseModel):
    scan_id: str
    node_id: str
    evidence: EvidenceResponse


class ErrorResponse(BaseModel):

    error: str
    detail: str


class AccessControlCheckRequest(BaseModel):
    auth_token: Optional[str] = None
    session_cookies: Optional[Dict[str, str]] = None


class AccessControlCheckResponse(BaseModel):
    scan_id: str
    evidence: EvidenceResponse
    finding: Dict[str, Any]
    node: Optional[NodeResponse] = None
    edge: Optional[EdgeResponse] = None

    model_config = ConfigDict(from_attributes=True)


class ReflectedInputCheckResponse(BaseModel):
    scan_id: str
    evidence: EvidenceResponse
    classification: Dict[str, Any]
    node: Optional[NodeResponse] = None
    edge: Optional[EdgeResponse] = None

    model_config = ConfigDict(from_attributes=True)


class AgentRunRequest(BaseModel):
    max_steps: Optional[int] = 15


class AgentRunResponse(BaseModel):
    scan_id: str
    total_steps: int
    max_steps: int
    steps: List[Dict[str, Any]]
    final_state: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)





