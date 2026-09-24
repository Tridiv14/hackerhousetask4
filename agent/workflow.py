import logging
from typing import Dict, Any, Literal
from agent.state import FraudInvestigationState
from agent.nodes import (
    initialize_case,
    plan_investigation,
    execute_graph_tools,
    generate_initial_nba,
    assess_sufficiency,
    request_external_evidence,
    generate_final_nba,
    evaluate_policy,
    authorize_and_execute,
    finalize_case
)

logger = logging.getLogger(__name__)

try:
    from langgraph.graph import StateGraph, END
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False

def should_continue_gathering(state: FraudInvestigationState) -> Literal["gather", "initial_nba"]:
    """Routes from plan_investigation to graph tools or to initial NBA."""
    # If the planner added tool_calls, execute them
    pending = [tc for tc in state.get("tool_calls", []) if tc.get("status") == "pending"]
    if pending:
        return "gather"
    return "initial_nba"

def should_request_evidence(state: FraudInvestigationState) -> Literal["request_evidence", "final_nba"]:
    """Routes based on sufficiency gate."""
    sufficient = state.get("evidence_sufficiency", {}).get("sufficient", False)
    # If not sufficient and we have gaps that external evidence can fill
    if not sufficient and state.get("evidence_sufficiency", {}).get("missing_evidence"):
        return "request_evidence"
    return "final_nba"

class FallbackStateGraphRunner:
    def stream(self, initial_state: FraudInvestigationState):
        state = dict(initial_state)
        
        state = initialize_case(state)
        yield {"initialize": state}
        
        max_iters = 3
        for _ in range(max_iters):
            state = plan_investigation(state)
            yield {"plan": state}
            if should_continue_gathering(state) == "initial_nba":
                break
            state = execute_graph_tools(state)
            yield {"execute_tools": state}
            
        state = generate_initial_nba(state)
        yield {"initial_nba": state}
        
        state = assess_sufficiency(state)
        yield {"sufficiency_gate": state}
        
        if should_request_evidence(state) == "request_evidence":
            state = request_external_evidence(state)
            yield {"request_evidence": state}
            
        state = generate_final_nba(state)
        yield {"final_nba": state}
        
        state = evaluate_policy(state)
        yield {"policy": state}
        
        state = authorize_and_execute(state)
        yield {"action": state}
        
        state = finalize_case(state)
        yield {"finalize": state}

    def invoke(self, initial_state: FraudInvestigationState) -> FraudInvestigationState:
        state = None
        for step in self.stream(initial_state):
            state = list(step.values())[0]
        return state

def build_fraud_investigation_graph():
    if HAS_LANGGRAPH:
        workflow = StateGraph(FraudInvestigationState)
        workflow.add_node("initialize", initialize_case)
        workflow.add_node("plan", plan_investigation)
        workflow.add_node("execute_tools", execute_graph_tools)
        workflow.add_node("initial_nba", generate_initial_nba)
        workflow.add_node("sufficiency_gate", assess_sufficiency)
        workflow.add_node("request_evidence", request_external_evidence)
        workflow.add_node("final_nba", generate_final_nba)
        workflow.add_node("policy", evaluate_policy)
        workflow.add_node("action", authorize_and_execute)
        workflow.add_node("finalize", finalize_case)

        workflow.set_entry_point("initialize")
        workflow.add_edge("initialize", "plan")
        
        workflow.add_conditional_edges(
            "plan",
            should_continue_gathering,
            {"gather": "execute_tools", "initial_nba": "initial_nba"}
        )
        workflow.add_edge("execute_tools", "plan")
        
        workflow.add_edge("initial_nba", "sufficiency_gate")
        
        workflow.add_conditional_edges(
            "sufficiency_gate",
            should_request_evidence,
            {"request_evidence": "request_evidence", "final_nba": "final_nba"}
        )
        
        workflow.add_edge("request_evidence", "final_nba")
        workflow.add_edge("final_nba", "policy")
        workflow.add_edge("policy", "action")
        workflow.add_edge("action", "finalize")
        workflow.add_edge("finalize", END)
        return workflow.compile()
    else:
        return FallbackStateGraphRunner()
