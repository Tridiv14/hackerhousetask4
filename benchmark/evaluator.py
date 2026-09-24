import os
import json
import logging
from typing import Dict, Any, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class Evaluator:
    """Phase 20: Separate Evaluator"""
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cases_dir = os.path.join(base_dir, "cases")
        self.report_path = os.path.join(base_dir, "benchmark", "evaluation_report.json")

    def evaluate(self):
        logger.info("Evaluating generated cases...")
        
        results = []
        schema_valid = 0
        total_cases = 0
        
        for file in os.listdir(self.cases_dir):
            if not file.endswith(".json"):
                continue
            
            total_cases += 1
            with open(os.path.join(self.cases_dir, file), "r") as f:
                try:
                    data = json.load(f)
                    
                    # Phase 17 Output Contract Validation
                    has_case = "case" in data
                    has_investigation = "investigation" in data
                    has_nba = "next_best_actions" in data
                    has_policy = "policy" in data
                    
                    is_valid = has_case and has_investigation and has_nba and has_policy
                    if is_valid:
                        schema_valid += 1
                        
                    results.append({
                        "case_id": data.get("case_id"),
                        "is_valid_schema": is_valid,
                        "verdict": data.get("case", {}).get("verdict"),
                        "tool_calls_made": data.get("investigation", {}).get("tool_calls", 0)
                    })
                except Exception as e:
                    logger.error(f"Error evaluating {file}: {e}")
                    
        summary = {
            "total_cases_evaluated": total_cases,
            "schema_compliance": f"{(schema_valid / total_cases * 100) if total_cases > 0 else 0:.2f}%",
            "detailed_results": results
        }
        
        with open(self.report_path, "w") as f:
            json.dump(summary, f, indent=2)
            
        logger.info(f"Evaluation complete. Schema compliance: {summary['schema_compliance']}")

if __name__ == "__main__":
    evaluator = Evaluator()
    evaluator.evaluate()

