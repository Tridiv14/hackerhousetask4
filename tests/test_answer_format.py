import os
import json
import unittest

class TestOfficialAnswerFormat(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.cases_dir = os.path.join(self.base_dir, "cases")

    def test_20_answer_files_exist(self):
        """Verify all 20 benchmark case answer files exist."""
        for i in range(1, 21):
            case_id = f"HHG-{i:03d}"
            case_path = os.path.join(self.cases_dir, f"{case_id}.json")
            self.assertTrue(os.path.exists(case_path), f"Missing answer file for {case_id}")

    def test_answer_file_schema(self):
        """Verify strict adherence to hackathon schema for all 20 answer files."""
        valid_patterns = {
            "card_testing", "card_not_present_fraud", "card_not_present_new_device",
            "out_of_region_use", "account_takeover", "undocumented", "none"
        }
        valid_verdicts = {"fraud", "legitimate", "uncertain"}
        valid_statuses = {"open", "closed_fraud", "closed_legitimate", "escalated"}
        valid_routes = {"auto", "L1", "L2"}

        for i in range(1, 21):
            case_id = f"HHG-{i:03d}"
            case_path = os.path.join(self.cases_dir, f"{case_id}.json")
            with open(case_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Top-level fields
            self.assertEqual(data.get("case_id"), case_id)
            self.assertIn("case", data)
            self.assertIn("evidence_requests", data)
            self.assertIn("next_best_actions", data)
            self.assertIn("sar", data)
            self.assertIn("stop_reason", data)
            self.assertIn("tool_calls", data)
            self.assertIn("tokens", data)
            self.assertIn("latency_s", data)

            # Part 1: case
            c = data["case"]
            self.assertIn(c.get("status"), valid_statuses)
            self.assertIn(c.get("verdict"), valid_verdicts)
            self.assertIsInstance(c.get("fraud_probability"), (int, float))
            self.assertIn(c.get("pattern"), valid_patterns)
            self.assertIsInstance(c.get("pattern_description"), str)
            self.assertIsInstance(c.get("affected_txn_ids"), list)
            self.assertIsInstance(c.get("first_suspicious_txn_id"), str)
            self.assertIsInstance(c.get("connected_card_ids"), list)
            self.assertIsInstance(c.get("connected_device_profiles"), list)
            self.assertIsInstance(c.get("exposure_usd"), (int, float))
            self.assertIsInstance(c.get("evidence"), list)
            self.assertIsInstance(c.get("similar_prior_cases"), list)
            self.assertIsInstance(c.get("summary"), str)
            self.assertIsInstance(c.get("written_to_graph"), bool)
            self.assertIsInstance(c.get("graph_case_id"), str)

            # Part 2: sar
            s = data["sar"]
            self.assertIsInstance(s.get("file"), bool)
            self.assertIsInstance(s.get("reason"), str)
            self.assertIsInstance(s.get("narrative"), str)
            self.assertIsInstance(s.get("subjects"), list)
            self.assertIsInstance(s.get("total_amount_usd"), (int, float))
            self.assertIsInstance(s.get("activity_dates"), list)

            # Part 3: next_best_actions
            nba = data["next_best_actions"]
            self.assertIn("initial", nba)
            self.assertIn("final", nba)
            self.assertIn("what_changed", nba)

            for act in nba["initial"]:
                self.assertIn("action", act)
                self.assertIn(act.get("route"), valid_routes)
                self.assertIn("reason", act)

            for act in nba["final"]:
                self.assertIn("action", act)
                self.assertIn(act.get("route"), valid_routes)
                self.assertIn("reason", act)

            # Policy rule: sar.file must agree with whether FILE_REPORT is in final actions
            final_action_names = [a["action"] for a in nba["final"]]
            has_file_report = "FILE_REPORT" in final_action_names
            self.assertEqual(s["file"], has_file_report, f"Mismatch in SAR filing for {case_id}")

if __name__ == "__main__":
    unittest.main()
