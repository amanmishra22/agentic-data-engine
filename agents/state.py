from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class PipelineState(TypedDict):
    """Mutable state dictionary passed across multi-domain LangGraph reasoning nodes."""

    raw_feed: List[Dict[str, Any]]
    validated_records: List[Dict[str, Any]]
    anomalies: List[Dict[str, Any]]
    prioritized_targets: List[Dict[str, Any]]
    domain_counts: Dict[str, int]
    executive_summary: Optional[str]
    dispatch_payloads: List[Dict[str, Any]]
