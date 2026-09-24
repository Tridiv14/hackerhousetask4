import logging
import json
from typing import Dict, Any, List
import os

logger = logging.getLogger(__name__)

class LLMReasoner:
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.1-pro") # Using a high reasoning model
        
    def _call_gemini(self, prompt: str) -> Dict[str, Any]:
        if not self.gemini_key:
            logger.warning("No GEMINI_API_KEY found, using dummy fallback logic.")
            return self._fallback_json(prompt)
            
        try:
            from google import genai
            client = genai.Client(api_key=self.gemini_key)
            response = client.models.generate_content(
                model=self.gemini_model,
                contents=prompt + "\n\nRespond strictly with a JSON object. No markdown formatting like ```json."
            )
            text = response.text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except Exception as e:
            logger.error(f"LLM Call failed: {e}")
            return self._fallback_json(prompt)

    def _fallback_json(self, prompt: str) -> Dict[str, Any]:
        """Provides naive mock responses if LLM fails or is missing key."""
        if "generate_plan" in prompt:
            return {
                "hypotheses": [{"hypothesis_id": "H1", "description": "Card-not-present fraud", "status": "ACTIVE"}],
                "evidence_gaps": ["Need identity telemetry"],
                "tool_calls": [{"tool_name": "get_identity_telemetry", "parameters": {"transaction_id": "unknown"}}]
            }
        elif "assess_sufficiency" in prompt:
            return {
                "sufficient": False,
                "reason": "Missing customer confirmation",
                "missing_evidence": ["Customer validation"],
                "blocking_conditions": ["Policy requires confirmation for high value"]
            }
        elif "generate_nba" in prompt:
            return {
                "nba": [
                    {"action": "VERIFY_WITH_CUSTOMER", "route": "auto", "reason": "Gather more info"},
                    {"action": "DECLINE_TRANSACTION", "route": "L1", "reason": "High risk"}
                ],
                "reason": "Pending verification",
                "evidence": ["High risk model score"],
                "uncertainty": "Unsure if customer made purchase"
            }
        return {}

    def generate_plan(self, case_id: str, trigger: Dict[str, Any], ledger: List[Dict[str, Any]], available_tools: List[str]) -> Dict[str, Any]:
        prompt = f"""
        You are a fraud investigation planner (Phase 5).
        Case ID: {case_id}
        Trigger: {json.dumps(trigger)}
        Evidence Ledger: {json.dumps(ledger, indent=2)}
        Available Tools: {json.dumps(available_tools)}
        
        Analyze the evidence gaps and formulate/update hypotheses (Phase 7).
        Hypothesis Status must be one of: ACTIVE, WEAKENED, SUPPORTED, REJECTED, UNRESOLVED.
        Return JSON with:
        - hypotheses: list of dict(hypothesis_id, description, supporting_evidence, contradicting_evidence, confidence, status)
        - evidence_gaps: list of strings
        - uncertainty_reasons: list of strings
        - tool_calls: list of dict(tool_name, parameters) from available_tools to fill gaps. If no gaps, return empty list.
        """
        return self._call_gemini(prompt)

    def assess_sufficiency(self, hypotheses: List[Dict], ledger: List[Dict], policy: str) -> Dict[str, Any]:
        prompt = f"""
        You are a sufficiency gate (Phase 8).
        Hypotheses: {json.dumps(hypotheses, indent=2)}
        Evidence Ledger: {json.dumps(ledger, indent=2)}
        Policy context: {policy}
        
        Determine if there is enough evidence to make a final decision without external customer outreach.
        Return JSON with:
        - sufficient: boolean
        - reason: string
        - missing_evidence: list of strings
        - blocking_conditions: list of strings
        """
        return self._call_gemini(prompt)

    def generate_initial_nba(self, hypotheses: List[Dict], ledger: List[Dict], uncertainty: List[str], missing_evidence: List[str]) -> Dict[str, Any]:
        prompt = f"""
        Generate Initial Next Best Action (Phase 10).
        Hypotheses: {json.dumps(hypotheses, indent=2)}
        Ledger: {json.dumps(ledger, indent=2)}
        Uncertainty: {json.dumps(uncertainty)}
        Missing Evidence: {json.dumps(missing_evidence)}
        
        Return JSON with:
        - initial_nba: list of dict(action, route, reason)
        - initial_reason: string
        - initial_evidence: list of strings (refs to ledger IDs)
        - initial_uncertainty: string
        - requested_evidence: string (what we will ask)
        - why_evidence_is_needed: string
        """
        return self._call_gemini(prompt)
        
    def generate_final_nba(self, initial_nba: Dict, ledger: List[Dict], hypotheses: List[Dict]) -> Dict[str, Any]:
        prompt = f"""
        Generate Final Next Best Action (Phase 11).
        Initial NBA context: {json.dumps(initial_nba, indent=2)}
        Final Ledger (includes received evidence): {json.dumps(ledger, indent=2)}
        Final Hypotheses: {json.dumps(hypotheses, indent=2)}
        
        Return JSON with:
        - final_nba: list of dict(action, route, reason)
        - final_reason: string
        - changed_from_initial: boolean
        - change_reason: string (explain why it changed or explicitly why it didn't)
        """
        return self._call_gemini(prompt)

    def evaluate_policy_and_authorization(self, final_nba: Dict[str, Any], trigger: Dict[str, Any], ledger: List[Dict]) -> Dict[str, Any]:
        prompt = f"""
        Evaluate Policy (Phase 12) & Authorization (Phase 13).
        Recommendations: {json.dumps(final_nba)}
        Trigger: {json.dumps(trigger)}
        
        Determine which actions are allowed based on deterministic rules (mock them based on exposure/fraud risk).
        Return JSON with:
        - policy_decision: dict(allowed: bool, required_evidence: list, policy_rule_ids: list, reason: string, violations: list)
        - approval_state: dict(approval_id: string, route: string, required_role: string, status: string, approver: string, decision: string, reason: string)
        - authorized_actions: list of dict(action, route, reason)
        """
        return self._call_gemini(prompt)
