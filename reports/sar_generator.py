import os
import json
import logging
from datetime import datetime
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class SARReportGenerator:
    """FinCEN Suspicious Activity Report (SAR) Document Generator."""

    def generate_sar_document(self, case_id: str, case_state: Dict[str, Any]) -> str:
        user = case_state.get("subgraph_context", {}).get("user") or {}
        raw = case_state.get("raw_case_data", {})
        struct = case_state.get("structuring_results", {})
        ring = case_state.get("ring_results", {})
        
        timestamp_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        sar_id = f"SAR-FINCEN-2024-{case_id}"

        narrative = []
        narrative.append("================================================================================")
        narrative.append("               DEPARTMENT OF THE TREASURY - FINCEN BSAR                 ")
        narrative.append("                 SUSPICIOUS ACTIVITY REPORT (SAR)                       ")
        narrative.append("================================================================================")
        narrative.append(f"FILING ID           : {sar_id}")
        narrative.append(f"CASE ID             : {case_id}")
        narrative.append(f"DATE PREPARED       : {timestamp_str}")
        narrative.append(f"FILING INSTITUTION  : Autonomous AI Fraud Investigation Core")
        narrative.append("--------------------------------------------------------------------------------")
        
        narrative.append("\nPART I: SUBJECT INFORMATION")
        narrative.append(f"  Subject Full Name  : {user.get('name', 'N/A')}")
        narrative.append(f"  Account ID / Ref   : {case_state.get('target_user')}")
        narrative.append(f"  Email Address      : {user.get('email', 'N/A')}")
        narrative.append(f"  Phone Number       : {user.get('phone', 'N/A')}")
        narrative.append(f"  Risk Profile Score : {user.get('risk_score', 0.0):.2f}")

        narrative.append("\nPART II: SUSPICIOUS ACTIVITY CLASSIFICATION")
        narrative.append(f"  Activity Type      : {raw.get('type', 'SUSPICIOUS_TRANSACTION')}")
        narrative.append(f"  Total Amount       : ${raw.get('total_amount', 0.0):,.2f}")
        narrative.append(f"  Structuring Flag   : {'YES' if struct.get('is_structuring_detected') else 'NO'}")
        narrative.append(f"  Fraud Ring Flag    : {'YES' if ring.get('is_ring_detected') else 'NO'}")

        narrative.append("\nPART III: DETAILED AGENT NARRATIVE & INVESTIGATION EVIDENCE")
        narrative.append(f"  Graph Analytics Summary:")
        narrative.append(f"  {case_state.get('graph_rag_summary', 'No graph summary recorded.')}")
        narrative.append("\n  Agent Reasoning & Compliance Determination:")
        narrative.append(f"  {case_state.get('fraud_reasoning', 'No reasoning recorded.')}")

        narrative.append("\nPART IV: ENFORCEMENT & REMEDIATION ACTIONS EXECUTED")
        for act in case_state.get("actions_taken", []):
            narrative.append(f"  - Action: {act.get('action')} | Status: {act.get('status')} | Details: {act.get('message')}")

        narrative.append("\n================================================================================")
        narrative.append("                   END OF OFFICIAL FINCEN SAR REPORT                            ")
        narrative.append("================================================================================")

        report_text = "\n".join(narrative)
        
        # Save report file
        reports_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(reports_dir, f"{sar_id}.txt")
        with open(output_path, "w") as f:
            f.write(report_text)
            
        logger.info(f"Generated official SAR report document: {output_path}")
        return report_text

if __name__ == "__main__":
    from agent.workflow import build_fraud_investigation_graph
    graph = build_fraud_investigation_graph()
    sample_state = graph.invoke({
        "case_id": "CASE-STR-001",
        "target_user": "user_str_1",
        "raw_case_data": {"case_id": "CASE-STR-001", "type": "STRUCTURING", "total_amount": 28500.0},
        "subgraph_context": {}, "structuring_results": {}, "ring_results": {},
        "graph_rag_summary": "", "risk_score": 0.0, "confidence_score": 0.0,
        "fraud_reasoning": "", "status": "INITIALIZED", "evidence_iteration": 0,
        "is_sar_required": True, "is_account_freeze_required": True,
        "is_card_block_required": True, "is_sms_warning_required": True,
        "requires_manager_approval": True, "actions_taken": [], "execution_logs": []
    })
    gen = SARReportGenerator()
    doc = gen.generate_sar_document("CASE-STR-001", sample_state)
    print(doc)
