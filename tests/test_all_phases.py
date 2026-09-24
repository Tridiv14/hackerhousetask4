import os
import unittest
import json
import importlib
from fastapi.testclient import TestClient

create_schema_mod = importlib.import_module("setup.01_create_schema")
SCHEMA_GSQL = create_schema_mod.SCHEMA_GSQL
create_schema = create_schema_mod.create_schema

load_data_mod = importlib.import_module("setup.02_load_data")
generate_benchmark_dataset = load_data_mod.generate_benchmark_dataset

from gsql.install_queries import GSQLQueryRunner
from agent.graph_rag import GraphRAGRetriever
from agent.workflow import build_fraud_investigation_graph, should_gather_more_evidence
from reports.sar_generator import SARReportGenerator
from backend.app import app

class TestFraudInvestigationSystem(unittest.TestCase):

    def test_phase1_schema(self):
        """Phase 1: Test TigerGraph GSQL Schema definition."""
        self.assertIn("CREATE VERTEX User", SCHEMA_GSQL)
        self.assertIn("CREATE GRAPH FraudInvestigation", SCHEMA_GSQL)
        success = create_schema()
        self.assertTrue(success)

    def test_phase1_dataset(self):
        """Phase 1: Test benchmark dataset generation."""
        dataset = generate_benchmark_dataset()
        cases = dataset.get("cases", [])
        self.assertEqual(len(cases), 20)
        types = set(c["type"] for c in cases)
        self.assertIn("STRUCTURING", types)
        self.assertIn("FRAUD_RING", types)
        self.assertIn("CARD_FRAUD", types)
        self.assertIn("LEGITIMATE", types)

    def test_phase2_gsql_queries(self):
        """Phase 2: Test GSQL query runner logic."""
        runner = GSQLQueryRunner()
        struct_res = runner.detect_structuring("user_str_1")
        self.assertTrue(struct_res["is_structuring_detected"])
        self.assertGreaterEqual(struct_res["total_structured_amount"], 10000.0)

        ring_res = runner.detect_fraud_ring("user_ring_1_a")
        self.assertTrue(ring_res["is_ring_detected"])

    def test_phase4_graph_rag(self):
        """Phase 4: Test GraphRAG context retriever."""
        retriever = GraphRAGRetriever()
        ctx = retriever.retrieve_context("user_str_1")
        self.assertIn("GraphRAG Evidence Context", ctx["summary_text"])
        self.assertIn("user_str_1", ctx["summary_text"])

    def test_phase3_langgraph_workflow(self):
        """Phase 3: Test LangGraph agent execution and confidence threshold routing."""
        graph = build_fraud_investigation_graph()
        initial_state = {
            "case_id": "CASE-STR-001",
            "target_user": "user_str_1",
            "raw_case_data": {"case_id": "CASE-STR-001", "type": "STRUCTURING", "total_amount": 28500.0},
            "subgraph_context": {}, "structuring_results": {}, "ring_results": {},
            "graph_rag_summary": "", "risk_score": 0.0, "confidence_score": 0.0,
            "fraud_reasoning": "", "status": "INITIALIZED", "evidence_iteration": 0,
            "is_sar_required": False, "is_account_freeze_required": False,
            "is_card_block_required": False, "is_sms_warning_required": False,
            "requires_manager_approval": False, "actions_taken": [], "execution_logs": []
        }
        final_state = graph.invoke(initial_state)
        self.assertIn(final_state["status"], ["CONFIRMED_FRAUD", "CLEARED"])
        self.assertTrue(len(final_state["execution_logs"]) > 0)

    def test_sar_generator(self):
        """Test FinCEN SAR report generator."""
        gen = SARReportGenerator()
        doc = gen.generate_sar_document("TEST-001", {
            "subgraph_context": {"user": {"name": "Test User", "email": "test@mail.com"}},
            "raw_case_data": {"type": "STRUCTURING", "total_amount": 15000.0},
            "structuring_results": {"is_structuring_detected": True},
            "ring_results": {"is_ring_detected": False},
            "graph_rag_summary": "Test Summary", "fraud_reasoning": "Test Reasoning",
            "actions_taken": []
        })
        self.assertIn("FINCEN BSAR", doc)
        self.assertIn("PART I: SUBJECT INFORMATION", doc)

    def test_phase5_fastapi_endpoints(self):
        """Phase 5: Test FastAPI REST routes."""
        client = TestClient(app)
        res = client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "HEALTHY")

        res_cases = client.get("/api/cases")
        self.assertEqual(res_cases.status_code, 200)
        self.assertGreaterEqual(res_cases.json()["total_cases"], 4)

if __name__ == "__main__":
    unittest.main()
