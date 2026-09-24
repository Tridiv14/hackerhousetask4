import os
import csv
import logging
import time
from typing import Dict, Any, List

from agent.workflow import build_fraud_investigation_graph

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class Runner:
    """Phase 1: Pure Execution Runner (No Evaluator logic)"""
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.dataset_path = os.path.join(base_dir, "data", "raw", "case_pack.csv")
        self.cases_dir = os.path.join(base_dir, "cases")
        os.makedirs(self.cases_dir, exist_ok=True)
        self.graph = build_fraud_investigation_graph()

    def load_cases(self) -> List[Dict[str, Any]]:
        cases = []
        with open(self.dataset_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cases.append({
                    "case_id": row["case_id"],
                    "target_user": row["customer_id"],
                    "trigger": {
                        "type": row["trigger_type"],
                        "text": row["trigger_text"],
                        "flagged_txn_id": row["flagged_txn_id"],
                        "card_id": row["card_id"],
                        "risk_score": float(row["risk_score"]) if row["risk_score"] else None
                    }
                })
        return cases

    def run(self):
        cases = self.load_cases()
        logger.info(f"Loaded {len(cases)} cases from case_pack.csv.")
        
        for case in cases:
            start_t = time.time()
            logger.info(f"--- Running Case {case['case_id']} ---")
            
            initial_state = {
                "case_id": case["case_id"],
                "target_user": case["target_user"],
                "trigger": case["trigger"]
            }
            
            self.graph.invoke(initial_state)
            
            # (Note: the workflow itself writes the final JSON to cases/<case_id>.json in the finalize_case node)
            latency = time.time() - start_t
            logger.info(f"--- Case {case['case_id']} completed in {latency:.2f}s ---")

if __name__ == "__main__":
    runner = Runner()
    runner.run()
