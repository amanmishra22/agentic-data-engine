from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict

class PipelineState(TypedDict):
    """Represents the mutable state machine passed across LangGraph nodes."""
    raw_feed: List[Dict[str, Any]]
    validated_records: List[Dict[str, Any]]
    anomalies: List[Dict[str, Any]]
    prioritized_targets: List[Dict[str, Any]]
    executive_summary: Optional[str]
    dispatch_payloads: List[Dict[str, Any]]
