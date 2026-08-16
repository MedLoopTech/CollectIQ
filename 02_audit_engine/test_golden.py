import json
from datetime import date
from pathlib import Path
from collectiq_engine import build_audit

HERE = Path(__file__).parent
expected = json.loads((HERE / "northstar_expected_output.json").read_text())
audit = build_audit(HERE / "northstar_sample.csv", date.fromisoformat(expected["as_of"]))
assert audit["status"] == "needs_review", audit

actual = audit["metrics"]
wanted = expected["metrics"]
keys = ["open_invoices","customers","total_ar","overdue_ar","ar_60_plus","ar_90_plus",
        "disputed_ar","missed_promise_value","priority_pool","top10_concentration",
        "overdue_ratio","ar_health_score"]

for key in keys:
    av, ev = actual[key], wanted[key]
    if isinstance(ev, float):
        assert abs(av - ev) <= 0.02, f"{key}: expected {ev}, got {av}"
    else:
        assert av == ev, f"{key}: expected {ev}, got {av}"

for i, exp in enumerate(expected["top_10_opportunities"]):
    act = audit["top_opportunities"][i]
    assert act["invoice_number"] == exp["invoice_number"], (i, act, exp)
    assert abs(act["priority_score"] - exp["priority_score"]) <= 0.01
    assert abs(act["outstanding"] - exp["outstanding"]) <= 0.02

print("PASS: Northstar golden dataset reconciles.")
print(json.dumps(actual, indent=2))
