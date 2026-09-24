import json
import csv

with open("benchmark/real_dataset.json") as f:
    data = json.load(f)

for c in data["cases"]:
    txs = c.get("transactions", [])
    ids = c.get("identities", {})
    hist = c.get("history_cases", [])
    flagged_id = c.get("flagged_txn_id")
    flagged_tx = next((t for t in txs if str(t.get("id")) == str(flagged_id)), {})
    
    # Check for card testing (small txns < $5 followed by larger)
    sorted_txs = sorted(txs, key=lambda x: x.get("timestamp", ""))
    small_txs = [t for t in sorted_txs if t.get("amount", 0.0) < 5.0]
    
    print("="*60)
    print(f"CASE: {c['case_id']} | Type: {c['type']} | Cust: {c['target_user']} | Card: {c['card_id']}")
    print(f"Trigger: {c['trigger_text']}")
    print(f"Flagged Txn #{flagged_id}: ${flagged_tx.get('amount')} | Risk Score: {flagged_tx.get('risk_score')} | Channel: {flagged_tx.get('channel')} | Location: {flagged_tx.get('location')}")
    print(f"Total Transactions: {len(txs)} | Small Txns (<$5): {len(small_txs)} | Device Profiles: {len(ids)} | Prior Cases: {len(hist)}")
    if hist:
        for h in hist[:2]:
            print(f"  Prior Case {h.get('case_id')}: Outcome={h.get('outcome')} | Pattern={h.get('pattern')} | Notes: {h.get('analyst_notes', '')[:90]}")
