import os
import time
import uuid
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

try:
    import pyTigerGraph as tg
    HAS_PYTIGERGRAPH = True
except ImportError:
    HAS_PYTIGERGRAPH = False

class TigerGraphExecutor:
    """Real pyTigerGraph executor with parameter binding, error handling, and provenance."""

    def __init__(self):
        self.host = os.getenv("TG_HOST", "http://localhost:9000")
        self.graphname = os.getenv("TG_GRAPH", "FraudInvestigation")
        self.username = os.getenv("TG_USERNAME", "tigergraph")
        self.password = os.getenv("TG_PASSWORD", "tigergraph")
        self.secret = os.getenv("TG_SECRET", "")
        self.conn = self._connect()

    def _connect(self):
        if not HAS_PYTIGERGRAPH:
            logger.warning("pyTigerGraph not found. Running in fallback mode.")
            return None

        try:
            conn = tg.TigerGraphConnection(
                host=self.host,
                graphname=self.graphname,
                username=self.username,
                password=self.password,
                gsqlSecret=self.secret
            )
            # Try getting a token
            if self.secret:
                conn.getToken(self.secret)
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to TigerGraph: {e}")
            return None

    def execute_query(self, query_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a GSQL query and wraps the result with provenance."""
        query_id = str(uuid.uuid4())
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        provenance = [f"Executed {query_name} on TigerGraph ({self.host})"]

        if self.conn is None:
            # Fallback to local execution if pyTigerGraph is not available or connection failed
            return self._fallback_execute(query_name, params, query_id, timestamp, provenance)

        try:
            raw_result = self.conn.runInstalledQuery(query_name, params, timeout=10000)
            
            entities = []
            relationships = []
            
            # pyTigerGraph returns a list of dictionaries, one per PRINT statement
            if isinstance(raw_result, list):
                for res_dict in raw_result:
                    for key, val in res_dict.items():
                        if isinstance(val, list):
                            for item in val:
                                if "v_id" in item:  # it's a vertex
                                    entities.append({
                                        "id": item["v_id"],
                                        "type": item["v_type"],
                                        "attributes": item.get("attributes", {})
                                    })
                                elif "from_id" in item and "to_id" in item: # it's an edge
                                    relationships.append({
                                        "from": item["from_id"],
                                        "to": item["to_id"],
                                        "type": item["e_type"],
                                        "attributes": item.get("attributes", {})
                                    })

            return {
                "query_id": query_id,
                "timestamp": timestamp,
                "entities": entities,
                "relationships": relationships,
                "observations": [], # observations usually derived in fallback, can add if needed
                "provenance": provenance
            }
        except Exception as e:
            logger.error(f"Query {query_name} failed: {e}")
            return {
                "query_id": query_id,
                "timestamp": timestamp,
                "error": str(e),
                "entities": [],
                "relationships": [],
                "observations": [],
                "provenance": provenance + [f"ERROR: {str(e)}"]
            }

    def _fallback_execute(self, query_name: str, params: Dict[str, Any], query_id: str, timestamp: str, provenance: List[str]) -> Dict[str, Any]:
        """Fallback emulator when TigerGraph is unavailable. Reads directly from clean CSV datasets to avoid label leakage."""
        import csv
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        datasets_dir = os.path.join(base_dir, "data", "raw")
        tx_path = os.path.join(datasets_dir, "transactions.csv")
        history_path = os.path.join(datasets_dir, "closed_cases_history.csv")
        identity_path = os.path.join(datasets_dir, "identity.csv")
        
        entities = []
        relationships = []
        observations = []
        
        if query_name == "get_customer_transaction_history":
            target_id = params.get("user_id") or params.get("customer_id")
            if target_id and os.path.exists(tx_path):
                with open(tx_path, "r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        if row.get("customer_id") == target_id:
                            entities.append({
                                "id": row.get("TransactionID"),
                                "type": "Transaction",
                                "attributes": {
                                    "amount": float(row.get("TransactionAmt", 0)),
                                    "timestamp": row.get("ts"),
                                    "channel": row.get("channel"),
                                    "product_cd": row.get("ProductCD")
                                }
                            })
                            relationships.append({"from": target_id, "to": row.get("TransactionID"), "type": "PERFORMED_TRANSACTION"})
            provenance.append("Fallback: read from transactions.csv")

        elif query_name == "get_transaction_context":
            tx_id = params.get("transaction_id")
            if tx_id and os.path.exists(tx_path):
                with open(tx_path, "r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        if row.get("TransactionID") == str(tx_id):
                            entities.append({"id": tx_id, "type": "Transaction", "attributes": dict(row)})
                            break
            provenance.append("Fallback: read from transactions.csv")

        elif query_name == "get_identity_telemetry":
            tx_id = str(params.get("transaction_id", ""))
            if tx_id and os.path.exists(identity_path):
                with open(identity_path, "r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        if row.get("TransactionID") == tx_id:
                            entities.append({"id": f"device_{tx_id}", "type": "Device", "attributes": dict(row)})
                            relationships.append({"from": tx_id, "to": f"device_{tx_id}", "type": "USED_DEVICE"})
                            break
            provenance.append("Fallback: read from identity.csv")

        elif query_name == "get_prior_cases_by_entity":
            target_id = params.get("customer_id") or params.get("card_id")
            if target_id and os.path.exists(history_path):
                with open(history_path, "r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        if row.get("customer_id") == target_id or row.get("card_id") == target_id:
                            entities.append({"id": row.get("case_id"), "type": "ClosedCase", "attributes": dict(row)})
                            relationships.append({"from": target_id, "to": row.get("case_id"), "type": "HAS_PRIOR_CASE"})
            provenance.append("Fallback: read from closed_cases_history.csv")
            
        elif query_name == "detect_structuring":
            # Very basic structuring simulation
            target_id = params.get("user_id") or params.get("customer_id")
            total_struct = 0.0
            tx_count = 0
            if target_id and os.path.exists(tx_path):
                with open(tx_path, "r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        if row.get("customer_id") == target_id:
                            amt = float(row.get("TransactionAmt", 0))
                            if 5000 <= amt < 10000:
                                total_struct += amt
                                tx_count += 1
                                entities.append({"id": row.get("TransactionID"), "type": "Transaction", "attributes": {"amount": amt}})
            if tx_count > 0:
                observations.append({
                    "pattern": "STRUCTURING",
                    "total_amount": total_struct,
                    "transaction_count": tx_count
                })
            provenance.append("Fallback: structuring detection on transactions.csv")
            
        elif query_name == "get_shared_device_cluster":
            # Retrieve shared devices
            device_id = params.get("device_id")
            if device_id and os.path.exists(identity_path) and os.path.exists(tx_path):
                # find txs with this device info
                shared_txs = []
                with open(identity_path, "r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        if row.get("DeviceInfo") == device_id or row.get("DeviceType") == device_id:
                            shared_txs.append(row.get("TransactionID"))
                            entities.append({"id": f"device_{row.get('TransactionID')}", "type": "Device", "attributes": dict(row)})
                
                # find customers for these txs
                if shared_txs:
                    with open(tx_path, "r", encoding="utf-8") as f:
                        for row in csv.DictReader(f):
                            if row.get("TransactionID") in shared_txs:
                                entities.append({"id": row.get("customer_id"), "type": "Customer", "attributes": {}})
                                relationships.append({"from": row.get("TransactionID"), "to": row.get("customer_id"), "type": "PERFORMED_BY"})
            provenance.append("Fallback: shared device lookup")
            
        elif query_name == "detect_card_testing_sequence":
            target_id = params.get("card_id")
            if target_id and os.path.exists(tx_path):
                txs = []
                with open(tx_path, "r", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        if row.get("card1") == target_id or row.get("card2") == target_id:
                            txs.append(row)
                
                small_txs = [t for t in txs if float(t.get("TransactionAmt", 0)) < 5.0]
                if len(small_txs) >= 2:
                    observations.append({"pattern": "CARD_TESTING", "small_tx_count": len(small_txs)})
            provenance.append("Fallback: card testing detection on transactions.csv")
            
        elif query_name == "write_case_to_graph":
            case_id = params.get("case_id")
            provenance.append(f"Fallback: mock writing case {case_id} to graph")

        return {
            "query_id": query_id,
            "timestamp": timestamp,
            "entities": entities,
            "relationships": relationships,
            "observations": observations,
            "provenance": provenance
        }

    # Helper methods for Graph Investigation Tools (Phase 4)
    def get_customer_transaction_history(self, customer_id: str):
        return self.execute_query("get_customer_transaction_history", {"customer_id": customer_id})

    def get_transaction_context(self, transaction_id: str):
        return self.execute_query("get_transaction_context", {"tx_id": transaction_id})
        
    def get_identity_telemetry(self, transaction_id: str):
        return self.execute_query("get_identity_telemetry", {"tx_id": transaction_id})

    def detect_structuring_pattern(self, customer_id: str):
        return self.execute_query("detect_structuring", {"customer_id": customer_id})

    def get_shared_device_cluster(self, device_id: str):
        return self.execute_query("get_shared_device_cluster", {"device_id": device_id})

    def get_prior_cases_by_entity(self, entity_id: str):
        return self.execute_query("get_prior_cases_by_entity", {"customer_id": entity_id, "card_id": entity_id})

    def detect_card_testing_sequence(self, card_id: str):
        return self.execute_query("detect_card_testing_sequence", {"card_id": card_id})
    
    def get_3hop_subgraph(self, start_entity_id: str, entity_type: str):
        return self.execute_query("get_3hop_subgraph", {"start_entity_id": start_entity_id, "entity_type": entity_type})
        
    def write_case_to_graph(self, case_id: str, case_data: Dict[str, Any]):
        return self.execute_query("write_case_to_graph", {"case_id": case_id, "case_data": str(case_data)})

