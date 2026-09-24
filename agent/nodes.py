import logging
import time
import uuid
import json
from typing import Dict, Any, List, Optional

from agent.state import FraudInvestigationState
from agent.graph_client import TigerGraphExecutor
from agent.llm_reasoner import LLMReasoner
from agent.actions import execute_action

logger = logging.getLogger(__name__)

graph_executor = TigerGraphExecutor()
llm_reasoner = LLMReasoner()

AVAILABLE_TOOLS = [
    "get_customer_transaction_history",
    "get_transaction_context",
    "get_identity_telemetry",
    "detect_structuring_pattern",
    "get_shared_device_cluster",
    "get_prior_cases_by_entity",
    "detect_card_testing_sequence"
]

def add_trace_event(state: FraudInvestigationState, stage: str, event: str, status: str = "completed", tool: str = None, query_id: str = None, duration_ms: int = 0, evidence_ids: List[str] = None, details: Dict = None):
    if "investigation_trace" not in state:
        state["investigation_trace"] = []
    
    trace = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stage": stage,
        "event": event,
        "status": status,
        "tool": tool,
        "query_id": query_id,
        "duration_ms": duration_ms,
        "evidence_ids": evidence_ids or [],
        "details": details or {}
    }
    state["investigation_trace"].append(trace)

def add_to_ledger(state: FraudInvestigationState, source: str, source_id: str, type_name: str, observation: str, confidence: float, query_id: str, provenance: str) -> None:
    """Phase 6: Evidence Ledger"""
    if "evidence_ledger" not in state:
        state["evidence_ledger"] = []
    
    item = {
        "evidence_id": f"EVID-{uuid.uuid4().hex[:8]}",
        "source": source,
        "source_id": source_id,
        "type": type_name,
        "observation": observation,
        "supports": [],
        "contradicts": [],
        "confidence": confidence,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "query_id": query_id,
        "provenance": provenance
    }
    state["evidence_ledger"].append(item)

def initialize_case(state: FraudInvestigationState) -> FraudInvestigationState:
    logger.info(f"Initializing case {state.get('case_id')}")
    state["status"] = "INITIALIZING"
    state["evidence_ledger"] = []
    state["hypotheses"] = []
    state["tool_calls"] = []
    state["uncertainty_reasons"] = []
    state["graph_query_provenance"] = []
    state["historical_matches"] = []
    state["investigation_trace"] = []
    state["execution_logs"] = [f"Initialized investigation for case {state['case_id']}"]
    state["timestamps"] = {"start": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    
    # Add initial trigger to ledger
    add_to_ledger(
        state, 
        source="trigger", 
        source_id="system", 
        type_name="INITIAL_ALERT", 
        observation=json.dumps(state.get("trigger", {})),
        confidence=1.0,
        query_id="N/A",
        provenance="Alert System"
    )
    
    add_trace_event(
        state, 
        stage="CASE", 
        event=f"Case initialized. Customer: {state.get('target_user')} | Risk score: {state.get('trigger', {}).get('risk_score', 'N/A')}",
        details={"trigger": state.get("trigger")}
    )
    
    return state

def plan_investigation(state: FraudInvestigationState) -> FraudInvestigationState:
    logger.info(f"Planning investigation for case {state.get('case_id')}")
    state["status"] = "PLANNING"
    
    plan_result = llm_reasoner.generate_plan(
        case_id=state["case_id"],
        trigger=state["trigger"],
        ledger=state["evidence_ledger"],
        available_tools=AVAILABLE_TOOLS
    )
    
    state["hypotheses"] = plan_result.get("hypotheses", state.get("hypotheses", []))
    state["uncertainty_reasons"] = plan_result.get("uncertainty_reasons", [])
    
    # Queue up tool calls
    queued = 0
    for tc in plan_result.get("tool_calls", []):
        tc["status"] = "pending"
        state["tool_calls"].append(tc)
        queued += 1
        
    add_trace_event(
        state,
        stage="HYPOTHESIS",
        event=f"Evaluated hypotheses. Queued {queued} tools.",
        details={"hypotheses": state["hypotheses"]}
    )
    
    state["execution_logs"].append(f"Planning phase updated hypotheses. Queued {len(plan_result.get('tool_calls', []))} tool calls.")
    return state

def execute_graph_tools(state: FraudInvestigationState) -> FraudInvestigationState:
    logger.info(f"Executing graph tools for case {state.get('case_id')}")
    state["status"] = "EVIDENCE_GATHERING"
    
    for tc in state["tool_calls"]:
        if tc.get("status") == "pending":
            tool_name = tc.get("tool_name")
            params = tc.get("parameters", {})
            
            start_time = time.time()
            res = graph_executor.execute_query(tool_name, params)
            duration_ms = int((time.time() - start_time) * 1000)
            
            state["graph_query_provenance"].append(res)
            
            is_fallback = any("Fallback" in p for p in res.get("provenance", []))
            backend_label = "LOCAL FALLBACK" if is_fallback else "TigerGraph"
            
            obs = f"Found {len(res.get('entities', []))} entities and {len(res.get('relationships', []))} relationships."
            if res.get("observations"):
                obs += f" Insights: {json.dumps(res.get('observations'))}"
            
            provenance_str = "; ".join(res.get("provenance", []))
            
            # Create a unique evidence ID manually so we can reference it in the trace
            evid_id = f"EVID-{uuid.uuid4().hex[:8]}"
            
            if "evidence_ledger" not in state:
                state["evidence_ledger"] = []
                
            item = {
                "evidence_id": evid_id,
                "source": "tigergraph" if not is_fallback else "local_csv",
                "source_id": res.get("query_id", ""),
                "type": f"GRAPH_RESULT:{tool_name}",
                "observation": obs,
                "supports": [],
                "contradicts": [],
                "confidence": 0.9,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "query_id": res.get("query_id", ""),
                "provenance": provenance_str
            }
            state["evidence_ledger"].append(item)
            
            tc["status"] = "completed"
            
            add_trace_event(
                state,
                stage="GRAPH_INVESTIGATION",
                event=f"Query {tool_name} completed via {backend_label}",
                status="completed",
                tool=tool_name,
                query_id=res.get("query_id"),
                duration_ms=duration_ms,
                evidence_ids=[evid_id],
                details={
                    "vertices": len(res.get("entities", [])),
                    "edges": len(res.get("relationships", [])),
                    "backend": backend_label
                }
            )
            
    return state

def assess_sufficiency(state: FraudInvestigationState) -> FraudInvestigationState:
    logger.info("Assessing evidence sufficiency (Phase 8)")
    state["status"] = "ASSESSING_SUFFICIENCY"
    
    policy_context = "SAR mandatory for >$10k or structuring. Card block required for confirmed fraud."
    res = llm_reasoner.assess_sufficiency(state["hypotheses"], state["evidence_ledger"], policy_context)
    
    state["evidence_sufficiency"] = res
    state["execution_logs"].append(f"Sufficiency check: {res.get('sufficient')}")
    
    add_trace_event(
        state,
        stage="ASSESSMENT",
        event=f"Evidence sufficiency: {'SUFFICIENT' if res.get('sufficient') else 'INSUFFICIENT'}",
        details=res
    )
    
    return state

def generate_initial_nba(state: FraudInvestigationState) -> FraudInvestigationState:
    logger.info("Generating Initial NBA (Phase 10)")
    state["status"] = "GENERATING_INITIAL_NBA"
    
    sufficiency = state.get("evidence_sufficiency", {})
    res = llm_reasoner.generate_initial_nba(
        state["hypotheses"], 
        state["evidence_ledger"],
        state["uncertainty_reasons"],
        sufficiency.get("missing_evidence", [])
    )
    
    state["initial_nba"] = res
    add_trace_event(state, stage="NBA", event="Initial recommendation generated", details=res)
    return state

def request_external_evidence(state: FraudInvestigationState) -> FraudInvestigationState:
    logger.info("Requesting external evidence (Phase 9)")
    state["status"] = "REQUESTING_EVIDENCE"
    
    nba = state.get("initial_nba", {})
    requested = nba.get("requested_evidence", "Customer validation of transactions")
    
    state["evidence_requests"] = [{"request": requested, "status": "sent"}]
    
    add_trace_event(state, stage="EVIDENCE", event=f"Requesting: {requested}")
    
    # Simulate response for benchmark
    simulated_response = "SIMULATED_RESPONSE: Customer denied unauthorized transactions."
    
    state["evidence_received"] = [{"request": requested, "response": simulated_response}]
    
    evid_id = f"EVID-{uuid.uuid4().hex[:8]}"
    item = {
        "evidence_id": evid_id,
        "source": "customer",
        "source_id": "SIM-1",
        "type": "CUSTOMER_RESPONSE",
        "observation": simulated_response,
        "supports": [],
        "contradicts": [],
        "confidence": 0.8,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "query_id": "N/A",
        "provenance": "Simulated interaction"
    }
    if "evidence_ledger" not in state:
        state["evidence_ledger"] = []
    state["evidence_ledger"].append(item)
    
    add_trace_event(state, stage="EVIDENCE", event="Response received", evidence_ids=[evid_id])
    add_trace_event(state, stage="REASSESS", event="Updating hypotheses based on new evidence")
    
    state["status"] = "EVIDENCE_RECEIVED"
    return state

def generate_final_nba(state: FraudInvestigationState) -> FraudInvestigationState:
    logger.info("Generating Final NBA (Phase 11)")
    state["status"] = "GENERATING_FINAL_NBA"
    
    res = llm_reasoner.generate_final_nba(
        state.get("initial_nba", {}),
        state["evidence_ledger"],
        state["hypotheses"]
    )
    
    state["final_nba"] = res
    add_trace_event(state, stage="NBA", event="Final recommendation generated", details=res)
    return state

def evaluate_policy(state: FraudInvestigationState) -> FraudInvestigationState:
    logger.info("Evaluating Policy and Authorization (Phase 12, 13)")
    state["status"] = "POLICY_CHECKED"
    
    res = llm_reasoner.evaluate_policy_and_authorization(
        state.get("final_nba", {}),
        state["trigger"],
        state["evidence_ledger"]
    )
    
    state["policy_decision"] = res.get("policy_decision")
    state["approval_state"] = res.get("approval_state")
    state["authorized_actions"] = res.get("authorized_actions", [])
    
    add_trace_event(state, stage="POLICY", event="Policy evaluated", details=res)
    if (res.get("approval_state") or {}).get("required"):
        add_trace_event(state, stage="AUTHORIZATION", event=f"{(res.get('approval_state') or {}).get('route')} approval required")
    
    return state

def authorize_and_execute(state: FraudInvestigationState) -> FraudInvestigationState:
    logger.info("Executing authorized actions (Phase 14)")
    state["status"] = "ACTION_EXECUTED"
    
    state["actions_executed"] = []
    for action in state.get("authorized_actions", []):
        logger.info(f"Executing: {action}")
        # In a real environment, we'd call the physical API
        result = execute_action(action)
        state["actions_executed"].append({
            "action": action,
            "result": "SUCCESS",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        })
        
    return state

def finalize_case(state: FraudInvestigationState) -> FraudInvestigationState:
    logger.info("Finalizing Case and Writing to Memory (Phase 15, 17)")
    state["status"] = "CASE_WRITTEN"
    state["timestamps"]["end"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    
    # Write back to graph
    res = graph_executor.write_case_to_graph(state["case_id"], {
        "status": "CLOSED",
        "hypotheses": state["hypotheses"],
        "actions": state["actions_executed"]
    })
    state["case_memory_write"] = res
    
    add_trace_event(state, stage="CASE", event="Investigation written to graph")
    
    # Final state
    state["status"] = "CLOSED_FRAUD" if state["hypotheses"] and state["hypotheses"][0].get("confidence", 0) > 0.7 else "CLOSED_LEGITIMATE"
    if (state.get("approval_state") or {}).get("required") and not state.get("actions_executed"):
        state["status"] = "AWAITING_HITL"
        
    add_trace_event(state, stage="COMPLETE", event="Investigation finished")
    
    # Format the final JSON Answer (Output Contract Phase 17)
    final_output = {
        "case_id": state["case_id"],
        "trigger": state.get("trigger", {}),
        "investigation": {
            "status": state["status"],
            "started_at": state["timestamps"]["start"],
            "completed_at": state["timestamps"]["end"],
            "trace": state["investigation_trace"],
            "tool_calls": state["tool_calls"]
        },
        "evidence": state["evidence_ledger"],
        "hypotheses": state["hypotheses"],
        "uncertainty": state.get("evidence_sufficiency", {}),
        "historical_matches": state.get("historical_matches", []),
        "initial_nba": state.get("initial_nba", {}),
        "evidence_requests": state.get("evidence_requests", []),
        "evidence_received": state.get("evidence_received", []),
        "final_nba": state.get("final_nba", {}),
        "policy_decision": state.get("policy_decision", {}),
        "approval": state.get("approval_state", {}),
        "actions": state.get("actions_executed", []),
        "case_memory": state.get("case_memory_write", {}),
        "stop_reason": state.get("stop_reason", "Completed full investigation loop."),
        "explanation": state.get("final_nba", {}).get("reasoning", "")
    }
    
    # Validate with Pydantic
    try:
        from pydantic import BaseModel
        class InvestigationOutput(BaseModel):
            case_id: str
            trigger: Dict[str, Any]
            investigation: Dict[str, Any]
            evidence: List[Dict[str, Any]]
            hypotheses: List[Dict[str, Any]]
            uncertainty: Dict[str, Any]
            historical_matches: List[Dict[str, Any]]
            initial_nba: Dict[str, Any]
            evidence_requests: List[Dict[str, Any]]
            evidence_received: List[Dict[str, Any]]
            final_nba: Dict[str, Any]
            policy_decision: Optional[Dict[str, Any]]
            approval: Optional[Dict[str, Any]]
            actions: List[Dict[str, Any]]
            case_memory: Dict[str, Any]
            stop_reason: str
            explanation: str
            
        InvestigationOutput(**final_output)
    except Exception as e:
        logger.error(f"Pydantic validation failed: {e}")
    
    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_file = os.path.join(base_dir, "cases", f"{state['case_id']}.json")
    
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2)
        
    return state
