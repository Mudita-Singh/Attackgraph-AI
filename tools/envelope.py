from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

class ToolOutputEnvelope(BaseModel):
    """
    Structured envelope specification adhering to Section 18.
    All security verification modules / tools wrap output using this schema.
    """
    tool: str = Field(..., description="Name of the tool executed (e.g., nmap, ffuf)")
    target: str = Field(..., description="Target URL/host executed against")
    raw_output: str = Field("", description="Raw console stdout/stderr or HTTP payload")
    parsed_findings: Dict[str, Any] = Field(default_factory=dict, description="Structured output extracted from raw response")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of execution finish")
