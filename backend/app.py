import os
import json
import asyncio
import logging
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from agent.workflow import build_fraud_investigation_graph
from agent.actions import execute_action

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Autonomous Fraud Investigation Agent API",
    description="Backend API and WebSocket stream engine powered by TigerGraph and LangGraph",
    version="1.0.0"
)

# Enable CORS for React/HTML frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CASES_DIR = os.path.join(BASE_DIR, "cases")
FRONTEND_INDEX = os.path.join(BASE_DIR, "frontend", "index.html")
EVAL_REPORT_PATH = os.path.join(BASE_DIR, "benchmark", "evaluation_report.json")

def load_case_pack() -> List[Dict[str, Any]]:
    import csv
    case_pack_path = os.path.join(BASE_DIR, "data", "raw", "case_pack.csv")
    cases = []
    if os.path.exists(case_pack_path):
        with open(case_pack_path, "r", encoding="utf-8") as f:
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

@app.get("/")
def serve_frontend():
    if os.path.exists(FRONTEND_INDEX):
        return FileResponse(FRONTEND_INDEX)
    return {"message": "Autonomous Fraud Investigation Agent API active"}

@app.get("/api/health")
def health_check():
    cases = load_case_pack()
    
    # Check TG Connection
    tg_status = "Offline"
    graph_schema = "Offline"
    gsql_queries = "Offline"
    from agent.graph_client import TigerGraphExecutor
    try:
        executor = TigerGraphExecutor()
        if executor.conn:
            tg_status = "Online"
            # Attempt a basic query to check schema/queries
            try:
                executor.conn.getEndpoints()
                graph_schema = "Online"
                gsql_queries = "Online"
            except:
                pass
    except Exception:
        pass

    return {
        "status": "HEALTHY" if tg_status == "Online" else "DEGRADED",
        "api": "Online",
        "case_pack": "Online" if cases else "Offline",
        "tigergraph": tg_status,
        "graph_schema": graph_schema,
        "gsql_queries": gsql_queries,
        "case_memory": "Online", # Assuming if TG is up, memory is accessible
        "llm_model": os.getenv("GEMINI_MODEL", "gemini-3.1-pro"),
        "has_gemini_key": bool(os.getenv("GEMINI_API_KEY"))
    }

@app.get("/api/benchmark")
def get_benchmark_results():
    if os.path.exists(EVAL_REPORT_PATH):
        with open(EVAL_REPORT_PATH, "r") as f:
            return json.load(f)
    return {"total_cases_evaluated": 0, "schema_compliance": "0%", "detailed_results": []}

@app.get("/api/cases")
def get_cases():
    cases = load_case_pack()
    return {"cases": cases, "total_cases": len(cases)}

@app.get("/api/cases/{case_id}")
def get_case_detail(case_id: str):
    case_file = os.path.join(CASES_DIR, f"{case_id}.json")
    if os.path.exists(case_file):
        with open(case_file, "r") as f:
            return json.load(f)
            
    # Fallback to case pack trigger info if case file not generated yet
    cases = load_case_pack()
    for c in cases:
        if c.get("case_id") == case_id:
            return c
    raise HTTPException(status_code=404, detail="Case not found")

@app.post("/api/investigate/{case_id}")
async def investigate_case(case_id: str):
    cases = load_case_pack()
    target_case = next((c for c in cases if c.get("case_id") == case_id), None)
    if not target_case:
        raise HTTPException(status_code=404, detail="Case not found")

    initial_state = {
        "case_id": case_id,
        "target_user": target_case["target_user"],
        "trigger": target_case["trigger"]
    }

    graph = build_fraud_investigation_graph()
    final_state = graph.invoke(initial_state)
    return final_state

class ManagerApprovalRequest(BaseModel):
    account_id: str
    case_id: str
    approved: bool

@app.post("/api/approve_freeze")
def approve_account_freeze(req: ManagerApprovalRequest):
    if not req.approved:
        return {"status": "REJECTED", "message": f"Account freeze for {req.account_id} rejected by manager."}
    
    res = execute_action({"action": "freeze_account", "route": "HUMAN_REVIEW", "target": req.account_id})
    return res

@app.websocket("/ws/investigate/{case_id}")
async def websocket_investigate(websocket: WebSocket, case_id: str):
    await websocket.accept()
    cases = load_case_pack()
    target_case = next((c for c in cases if c.get("case_id") == case_id), None)
    
    if not target_case:
        await websocket.send_json({"event": "error", "message": "Case not found"})
        await websocket.close()
        return

    try:
        await websocket.send_json({"event": "step", "node": "start", "log": f"Started agent investigation stream for {case_id}"})
        await asyncio.sleep(0.3)

        initial_state = {
            "case_id": case_id,
            "target_user": target_case["target_user"],
            "trigger": target_case["trigger"]
        }

        graph = build_fraud_investigation_graph()
        
        final_state = None
        for step_idx, event in enumerate(graph.stream(initial_state)):
            for node, state in event.items():
                final_state = state
                await websocket.send_json({
                    "event": "step",
                    "node": node,
                    "log": state.get("execution_logs", [""])[-1] if state.get("execution_logs") else f"Completed {node}",
                    "state": state
                })
                await asyncio.sleep(0.1)

        await websocket.send_json({"event": "complete", "result": final_state})

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected for case {case_id}")
    except Exception as e:
        logger.error(f"Error in WebSocket investigation: {e}")
        await websocket.send_json({"event": "error", "message": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
