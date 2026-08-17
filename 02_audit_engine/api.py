from datetime import date
from pathlib import Path
import math
import tempfile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile

from collectiq_engine import (
    build_audit,
    canonicalize,
    read_input,
    score_invoices,
)

app = FastAPI(title="CollectIQ Audit Engine", version="0.2.0")


def _clean(value):
    """Return a JSON-safe scalar for the compact Sprint seed."""
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    try:
        if math.isnan(float(value)):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        value = value.item()
    return value


def build_sprint_seed(path: Path, audit_date: date):
    """Build a compact but complete Day-0 portfolio for Recovery Sprint conversion."""
    raw = read_input(path)
    canonical, _ = canonicalize(raw)
    scored = score_invoices(canonical, audit_date)
    open_df = scored[scored["outstanding_amount"] > 0].copy()

    accounts = []
    for customer_name, group in open_df.groupby("customer_name", dropna=False):
        overdue = group[group["days_overdue"] > 0]
        accounts.append({
            "customer_name": str(customer_name),
            "external_customer_id": str(group.iloc[0].get("customer_id", "") or ""),
            "contact_email": str(group.iloc[0].get("email", "") or ""),
            "sales_owner": str(group.iloc[0].get("sales_owner", "") or ""),
            "total_outstanding": round(float(group["outstanding_amount"].sum()), 2),
            "overdue_amount": round(float(overdue["outstanding_amount"].sum()), 2),
            "priority_score": round(float(group["priority_score"].max()), 1),
            "priority_band": str(group.sort_values("priority_score", ascending=False).iloc[0]["priority_band"]),
        })

    invoices = []
    for _, row in open_df.iterrows():
        invoices.append({
            "customer_name": str(row["customer_name"]),
            "invoice_number": str(row["invoice_number"]),
            "invoice_date": _clean(row.get("invoice_date")),
            "due_date": _clean(row.get("due_date")),
            "currency": str(row.get("currency") or "USD"),
            "invoice_amount": round(float(row.get("invoice_amount") or 0), 2),
            "outstanding_amount": round(float(row.get("outstanding_amount") or 0), 2),
            "days_overdue": int(row.get("days_overdue") or 0),
            "age_bucket": str(row.get("age_bucket") or ""),
            "priority_score": round(float(row.get("priority_score") or 0), 1),
            "priority_band": str(row.get("priority_band") or ""),
            "recommended_action": str(row.get("recommended_action") or ""),
            "promise_status": str(row.get("promise_status") or ""),
            "promise_amount": round(float(row.get("promise_amount") or 0), 2),
            "promise_date": _clean(row.get("promise_date")),
            "dispute_type": str(row.get("dispute_type") or ""),
        })

    return {
        "seed_version": "0.1",
        "as_of": audit_date.isoformat(),
        "accounts": accounts,
        "invoices": invoices,
    }


@app.get("/health")
def health():
    return {"ok": True, "service": "collectiq-audit-engine", "version": "0.2.0"}


@app.post("/audit/upload")
async def audit_upload(file: UploadFile = File(...), as_of: str | None = Form(default=None)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".csv", ".xlsx", ".xls"):
        raise HTTPException(400, "Unsupported file type.")

    audit_date = date.fromisoformat(as_of) if as_of else date.today()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        result = build_audit(tmp_path, audit_date)
        result["source_file"] = file.filename

        # Only attach seed data to a valid audit. It is stored with audit_summary
        # and becomes the authoritative Day-0 input for a paid Recovery Sprint.
        if result.get("status") != "validation_failed":
            result["sprint_seed"] = build_sprint_seed(tmp_path, audit_date)

        return result
    finally:
        tmp_path.unlink(missing_ok=True)
