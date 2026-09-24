from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime

class FraudInvestigationState(TypedDict):
    case_id: str
    target_user: str
    trigger: Dict[str, Any]
    
    # Core state
    status: str
    stop_reason: Optional[str]
    
    # Evidence & Hypotheses
    evidence_ledger: List[Dict[str, Any]]
    hypotheses: List[Dict[str, Any]]
    uncertainty_reasons: List[str]
    tool_calls: List[Dict[str, Any]]
    graph_query_provenance: List[Dict[str, Any]]
    historical_matches: List[Dict[str, Any]]
    
    # Decision Making
    initial_nba: Optional[Dict[str, Any]]
    evidence_requests: List[Dict[str, Any]]
    evidence_received: List[Dict[str, Any]]
    final_nba: Optional[Dict[str, Any]]
    
    # Policy & Action
    policy_decision: Optional[Dict[str, Any]]
    approval_state: Optional[Dict[str, Any]]
    actions_executed: List[Dict[str, Any]]
    case_memory_write: Optional[Dict[str, Any]]
    
    # Tracing
    execution_logs: List[str]
    investigation_trace: List[Dict[str, Any]]
    timestamps: Dict[str, str]
