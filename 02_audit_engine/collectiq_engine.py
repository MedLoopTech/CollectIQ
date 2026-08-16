#!/usr/bin/env python3
"""
CollectIQ Audit Engine v0.1
Deterministic AR intelligence engine for CSV/XLSX ageing files.

Usage:
  python collectiq_engine.py input.csv --as-of 2026-08-16 --output audit.json
  python collectiq_engine.py input.xlsx --output audit.json

No LLM is required for calculations.
"""

from __future__ import annotations
import argparse
import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd


ENGINE_VERSION = "0.1.0"

ALIASES = {
    "customer_name": [
        "customer_name","customer","client","client_name","account","account_name",
        "debtor","debtor_name","customer name","client name","account name"
    ],
    "customer_id": [
        "customer_id","customer id","client_id","client id","account_id","account id",
        "debtor_id","debtor id"
    ],
    "invoice_number": [
        "invoice_number","invoice number","invoice_no","invoice no","invoice #","invoice#",
        "inv_no","inv no","document_number","document number","document no"
    ],
    "invoice_date": [
        "invoice_date","invoice date","date","document_date","document date","posting_date","posting date"
    ],
    "due_date": [
        "due_date","due date","payment_due_date","payment due date","maturity_date","maturity date"
    ],
    "invoice_amount": [
        "invoice_amount","invoice amount","gross_amount","gross amount","original_amount","original amount",
        "amount","invoice value","invoice_value"
    ],
    "amount_paid": [
        "amount_paid","amount paid","paid_amount","paid amount","payments","payment_amount","payment amount"
    ],
    "outstanding_amount": [
        "outstanding_amount","outstanding amount","outstanding","open_amount","open amount","balance",
        "balance_due","balance due","remaining_amount","remaining amount","open balance"
    ],
    "currency": ["currency","curr","currency_code","currency code"],
    "payment_terms_days": [
        "payment_terms_days","payment terms days","payment_terms","payment terms","terms","credit_terms","credit terms"
    ],
    "avg_days_late": [
        "avg_days_late","average_days_late","average days late","avg days late","avg_lateness","average lateness"
    ],
    "promise_reliability": [
        "promise_reliability","promise reliability","promise_reliability_score","promise reliability score"
    ],
    "last_contact_days": [
        "last_contact_days","days_since_last_contact","days since last contact","last contact days"
    ],
    "promise_status": [
        "promise_status","promise status","ptp_status","ptp status","promise_to_pay_status","promise to pay status"
    ],
    "promise_amount": [
        "promise_amount","promise amount","ptp_amount","ptp amount","promised_amount","promised amount"
    ],
    "promise_date": [
        "promise_date","promise date","ptp_date","ptp date","promised_date","promised date"
    ],
    "dispute_type": [
        "dispute_type","dispute type","dispute","dispute_reason","dispute reason","blocker","blocker_type","blocker type"
    ],
    "sales_owner": [
        "sales_owner","sales owner","account_owner","account owner","owner","relationship_manager","relationship manager"
    ],
    "email": [
        "email","customer_email","customer email","contact_email","contact email","billing_email","billing email"
    ],
}

REQUIRED = ["customer_name", "invoice_number", "invoice_date", "due_date", "outstanding_amount"]

DISPUTE_NORMALIZATION = {
    "po":"purchase_order","purchase order":"purchase_order","purchase_order":"purchase_order",
    "missing document":"missing_document","missing docs":"missing_document","missing_document":"missing_document",
    "invoice error":"invoice_error","invoice_error":"invoice_error","billing error":"invoice_error",
    "approval pending":"approval_pending","approval_pending":"approval_pending",
    "pricing":"pricing","price":"pricing","pricing issue":"pricing",
    "legal":"legal","legal dispute":"legal",
}

PROMISE_NORMALIZATION = {
    "missed":"missed","broken":"missed","failed":"missed",
    "pending":"pending","open":"pending","due":"pending",
    "kept":"kept","fulfilled":"kept","paid":"kept",
    "partially kept":"partially_kept","partial":"partially_kept",
}


def _norm(s: Any) -> str:
    if s is None:
        s = ""
    else:
        try:
            if pd.isna(s):
                s = ""
        except Exception:
            pass
    s = str(s)
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def infer_mapping(columns: Iterable[str]) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    normalized = {_norm(c): c for c in columns}
    mapping: Dict[str, str] = {}
    collisions: Dict[str, List[str]] = {}
    for canonical, aliases in ALIASES.items():
        matches = []
        for alias in aliases:
            n = _norm(alias)
            if n in normalized:
                matches.append(normalized[n])
        if matches:
            mapping[canonical] = matches[0]
            if len(set(matches)) > 1:
                collisions[canonical] = list(dict.fromkeys(matches))
    return mapping, collisions


def read_input(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Input file not found: {p}")
    ext = p.suffix.lower()
    if ext == ".csv":
        return pd.read_csv(p)
    if ext in (".xlsx", ".xls"):
        return pd.read_excel(p)
    raise ValueError("Unsupported file type. Use CSV, XLSX, or XLS.")


def _to_numeric(series: pd.Series) -> pd.Series:
    if series.dtype == object:
        cleaned = (
            series.astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("$", "", regex=False)
            .str.replace("£", "", regex=False)
            .str.replace("€", "", regex=False)
            .str.strip()
            .replace({"": None, "nan": None, "None": None})
        )
        return pd.to_numeric(cleaned, errors="coerce")
    return pd.to_numeric(series, errors="coerce")


def _to_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.date


def canonicalize(df: pd.DataFrame, explicit_mapping: Optional[Dict[str, str]] = None) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    inferred, collisions = infer_mapping(df.columns)
    mapping = dict(inferred)
    if explicit_mapping:
        mapping.update(explicit_mapping)

    missing = [x for x in REQUIRED if x not in mapping]
    if missing:
        raise ValueError(
            "Missing required columns after mapping: "
            + ", ".join(missing)
            + ". Detected columns: "
            + ", ".join(map(str, df.columns))
        )

    out = pd.DataFrame()
    for canonical, source in mapping.items():
        if source in df.columns:
            out[canonical] = df[source]

    # Defaults / derivations
    if "customer_id" not in out:
        out["customer_id"] = out["customer_name"].astype(str)
    if "invoice_amount" not in out:
        out["invoice_amount"] = _to_numeric(out["outstanding_amount"])
    if "amount_paid" not in out:
        out["amount_paid"] = 0.0
    if "currency" not in out:
        out["currency"] = "USD"
    if "avg_days_late" not in out:
        out["avg_days_late"] = 0
    if "promise_reliability" not in out:
        out["promise_reliability"] = None
    if "last_contact_days" not in out:
        out["last_contact_days"] = 999
    if "promise_status" not in out:
        out["promise_status"] = ""
    if "promise_amount" not in out:
        out["promise_amount"] = 0.0
    if "promise_date" not in out:
        out["promise_date"] = None
    if "dispute_type" not in out:
        out["dispute_type"] = ""
    if "sales_owner" not in out:
        out["sales_owner"] = ""
    if "email" not in out:
        out["email"] = ""

    # Types
    for c in ("invoice_amount","amount_paid","outstanding_amount","avg_days_late",
              "promise_reliability","last_contact_days","promise_amount","payment_terms_days"):
        if c in out:
            out[c] = _to_numeric(out[c])

    for c in ("invoice_date","due_date","promise_date"):
        if c in out:
            out[c] = _to_date(out[c])

    # Normalize text
    out["customer_name"] = out["customer_name"].astype(str).str.strip()
    out["invoice_number"] = out["invoice_number"].astype(str).str.strip()
    out["promise_status"] = out["promise_status"].apply(
        lambda x: PROMISE_NORMALIZATION.get(_norm(x), _norm(x).replace(" ", "_")) if _norm(x) else ""
    )
    out["dispute_type"] = out["dispute_type"].apply(
        lambda x: DISPUTE_NORMALIZATION.get(_norm(x), _norm(x).replace(" ", "_")) if _norm(x) else ""
    )

    info = {
        "mapping": mapping,
        "mapping_collisions": collisions,
        "original_columns": list(map(str, df.columns)),
    }
    return out, info


def validate(df: pd.DataFrame) -> Dict[str, Any]:
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    def add(kind: str, row: int, field: str, message: str):
        rec = {"row": int(row) + 2, "field": field, "message": message}
        (errors if kind == "error" else warnings).append(rec)

    for idx, row in df.iterrows():
        if not str(row.get("customer_name","")).strip():
            add("error", idx, "customer_name", "Customer name is missing.")
        if not str(row.get("invoice_number","")).strip():
            add("error", idx, "invoice_number", "Invoice number is missing.")
        if pd.isna(row.get("invoice_date")):
            add("error", idx, "invoice_date", "Invoice date is invalid or missing.")
        if pd.isna(row.get("due_date")):
            add("error", idx, "due_date", "Due date is invalid or missing.")
        if pd.isna(row.get("outstanding_amount")):
            add("error", idx, "outstanding_amount", "Outstanding amount is invalid or missing.")
        elif float(row["outstanding_amount"]) < 0:
            add("error", idx, "outstanding_amount", "Outstanding amount cannot be negative.")

        inv_amt = row.get("invoice_amount")
        out_amt = row.get("outstanding_amount")
        if pd.notna(inv_amt) and pd.notna(out_amt) and float(out_amt) > float(inv_amt) + 0.01:
            add("warning", idx, "outstanding_amount", "Outstanding amount exceeds invoice amount.")

        if pd.notna(row.get("invoice_date")) and pd.notna(row.get("due_date")):
            if row["due_date"] < row["invoice_date"]:
                add("warning", idx, "due_date", "Due date is before invoice date.")

    dupes = df["invoice_number"].astype(str).duplicated(keep=False)
    for idx in df.index[dupes]:
        add("warning", idx, "invoice_number", "Duplicate invoice number detected.")

    currencies = sorted(set(x for x in df["currency"].astype(str).str.strip() if x))
    if len(currencies) > 1:
        warnings.append({
            "row": None,
            "field": "currency",
            "message": f"Multiple currencies detected ({', '.join(currencies)}). Portfolio totals are not FX-normalized."
        })

    return {
        "valid": len(errors) == 0,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "errors": errors[:200],
        "warnings": warnings[:200],
        "row_count": int(len(df)),
    }


def age_bucket(days: int) -> str:
    if days <= 0: return "Current"
    if days <= 30: return "1-30"
    if days <= 60: return "31-60"
    if days <= 90: return "61-90"
    return "90+"


def age_score(days: int) -> int:
    if days <= 0: return 0
    if days <= 15: return 20
    if days <= 30: return 35
    if days <= 45: return 55
    if days <= 60: return 70
    if days <= 90: return 85
    return 100


def amount_score(percentile: float) -> int:
    if percentile >= .90: return 100
    if percentile >= .75: return 80
    if percentile >= .50: return 60
    if percentile >= .25: return 40
    return 20


def promise_risk(status: str, pdate: Optional[date], as_of: date) -> int:
    if status == "missed": return 100
    if status == "pending" and pdate:
        d = (pdate - as_of).days
        if d <= 0: return 90
        if d <= 3: return 70
        return 20
    return 40


def behavior_score(avg_late: float) -> int:
    x = 0 if pd.isna(avg_late) else float(avg_late)
    if x > 45: return 100
    if x > 30: return 80
    if x > 15: return 60
    if x > 0: return 35
    return 10


def contact_score(days: float) -> int:
    x = 999 if pd.isna(days) else float(days)
    if x > 14: return 90
    if x >= 8: return 70
    if x >= 4: return 40
    return 10


def dispute_score(dispute: str) -> int:
    return {
        "": 30,
        "missing_document": 90,
        "purchase_order": 80,
        "approval_pending": 70,
        "invoice_error": 70,
        "pricing": 40,
        "legal": 0,
    }.get(dispute, 30)


def priority_band(score: float) -> str:
    if score >= 85: return "Critical"
    if score >= 70: return "High"
    if score >= 50: return "Elevated"
    if score >= 30: return "Moderate"
    return "Low"


def recommended_action(row: pd.Series) -> str:
    if row["dispute_type"] == "legal":
        return "Route to human/legal review; pause automated collection activity."
    if row["promise_status"] == "missed":
        return "Follow up on missed payment commitment."
    if row["dispute_type"]:
        return f"Resolve {row['dispute_type'].replace('_',' ')} before generic follow-up."
    if row["last_contact_days"] > 14 and row["days_overdue"] > 0:
        return "Immediate follow-up; no recent contact recorded."
    if row["priority_score"] >= 70:
        return "High-priority collection follow-up."
    if row["days_overdue"] > 0:
        return "Standard collection follow-up."
    return "Monitor; not yet overdue."


def score_invoices(df: pd.DataFrame, as_of: date) -> pd.DataFrame:
    out = df.copy()

    out["days_overdue"] = out["due_date"].apply(
        lambda d: (as_of - d).days if pd.notna(d) else 0
    )
    out["age_bucket"] = out["days_overdue"].apply(age_bucket)

    # Percentile rank within current portfolio
    ranks = out["outstanding_amount"].rank(method="max", pct=True)
    out["age_score"] = out["days_overdue"].apply(age_score)
    out["amount_score"] = ranks.apply(amount_score)
    out["promise_risk"] = out.apply(
        lambda r: promise_risk(r["promise_status"], r["promise_date"], as_of), axis=1
    )
    out["behavior_score"] = out["avg_days_late"].apply(behavior_score)
    out["contact_score"] = out["last_contact_days"].apply(contact_score)
    out["dispute_opportunity_score"] = out["dispute_type"].apply(dispute_score)

    out["priority_score"] = (
        .30 * out["age_score"] +
        .25 * out["amount_score"] +
        .15 * out["promise_risk"] +
        .10 * out["behavior_score"] +
        .10 * out["contact_score"] +
        .10 * out["dispute_opportunity_score"]
    ).round(1)

    out["priority_band"] = out["priority_score"].apply(priority_band)
    out["recommended_action"] = out.apply(recommended_action, axis=1)

    return out


def portfolio_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    open_df = df[df["outstanding_amount"] > 0].copy()
    total = float(open_df["outstanding_amount"].sum())
    overdue_df = open_df[open_df["days_overdue"] > 0]
    overdue = float(overdue_df["outstanding_amount"].sum())
    ar60 = float(open_df.loc[open_df["days_overdue"] > 60, "outstanding_amount"].sum())
    ar90 = float(open_df.loc[open_df["days_overdue"] > 90, "outstanding_amount"].sum())
    disputed = float(open_df.loc[open_df["dispute_type"].astype(str) != "", "outstanding_amount"].sum())
    missed = float(open_df.loc[open_df["promise_status"] == "missed", "promise_amount"].fillna(0).sum())
    priority_pool = float(open_df.loc[
        (open_df["days_overdue"] > 0) & (open_df["priority_score"] >= 70),
        "outstanding_amount"
    ].sum())

    cust = open_df.groupby("customer_name", dropna=False)["outstanding_amount"].sum().sort_values(ascending=False)
    top10 = float(cust.head(10).sum())
    top10_concentration = top10 / total if total else 0.0

    overdue_ratio = overdue / total if total else 0.0
    ar60_ratio = ar60 / total if total else 0.0
    ar90_ratio = ar90 / total if total else 0.0
    dispute_ratio = disputed / total if total else 0.0

    if overdue:
        contact_gap_value = float(overdue_df.loc[overdue_df["last_contact_days"] > 14, "outstanding_amount"].sum())
        contact_gap_ratio = contact_gap_value / overdue
    else:
        contact_gap_ratio = 0.0

    matured = open_df[open_df["promise_status"].isin(["missed","kept","partially_kept"])]
    if len(matured):
        missed_rate = float((matured["promise_status"] == "missed").sum()) / len(matured)
    else:
        missed_rate = 0.0

    health = 100 - (
        25 * min(overdue_ratio / .50, 1) +
        20 * min(ar60_ratio / .25, 1) +
        15 * min(ar90_ratio / .15, 1) +
        15 * min(top10_concentration / .70, 1) +
        10 * missed_rate +
        10 * min(dispute_ratio / .15, 1) +
        5 * min(contact_gap_ratio / .50, 1)
    )
    health = max(0, min(100, round(health, 1)))

    if health >= 80: health_label = "Healthy"
    elif health >= 65: health_label = "Watch"
    elif health >= 50: health_label = "Weak"
    else: health_label = "Critical"

    return {
        "open_invoices": int(len(open_df)),
        "customers": int(open_df["customer_name"].nunique(dropna=True)),
        "total_ar": round(total, 2),
        "overdue_ar": round(overdue, 2),
        "ar_60_plus": round(ar60, 2),
        "ar_90_plus": round(ar90, 2),
        "disputed_ar": round(disputed, 2),
        "missed_promise_value": round(missed, 2),
        "priority_pool": round(priority_pool, 2),
        "top10_concentration": round(top10_concentration, 6),
        "overdue_ratio": round(overdue_ratio, 6),
        "ar_health_score": health,
        "ar_health_label": health_label,
    }


def top_opportunities(df: pd.DataFrame, n: int = 10) -> List[Dict[str, Any]]:
    work = df[(df["outstanding_amount"] > 0) & (df["days_overdue"] > 0)].copy()
    work = work.sort_values(["priority_score","outstanding_amount"], ascending=[False,False]).head(n)
    rows = []
    for _, r in work.iterrows():
        rows.append({
            "customer": str(r["customer_name"]),
            "invoice_number": str(r["invoice_number"]),
            "outstanding": round(float(r["outstanding_amount"]), 2),
            "days_overdue": int(r["days_overdue"]),
            "priority_score": round(float(r["priority_score"]), 1),
            "priority_band": str(r["priority_band"]),
            "promise_status": str(r["promise_status"]) if r["promise_status"] else None,
            "dispute_type": str(r["dispute_type"]) if r["dispute_type"] else None,
            "recommended_action": str(r["recommended_action"]),
            "why": [
                f"{int(r['days_overdue'])} days overdue",
                f"amount score {int(r['amount_score'])}/100",
                f"age score {int(r['age_score'])}/100",
                *([f"promise status: {r['promise_status']}"] if r["promise_status"] else []),
                *([f"blocker: {r['dispute_type'].replace('_',' ')}"] if r["dispute_type"] else []),
                *([f"{int(r['last_contact_days'])} days since last contact"] if r["last_contact_days"] > 14 else []),
            ],
        })
    return rows


def blocker_summary(df: pd.DataFrame) -> List[Dict[str, Any]]:
    work = df[(df["outstanding_amount"] > 0) & (df["dispute_type"].astype(str) != "")]
    if work.empty:
        return []
    grouped = work.groupby("dispute_type")["outstanding_amount"].agg(["sum","count"]).sort_values("sum", ascending=False)
    return [
        {"blocker": idx, "amount": round(float(row["sum"]), 2), "invoice_count": int(row["count"])}
        for idx, row in grouped.iterrows()
    ]


def build_audit(
    path: str | Path,
    as_of: Optional[date] = None,
    explicit_mapping: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    as_of = as_of or date.today()
    raw = read_input(path)
    canonical, mapping_info = canonicalize(raw, explicit_mapping)
    validation = validate(canonical)
    if not validation["valid"]:
        return {
            "engine_version": ENGINE_VERSION,
            "as_of": as_of.isoformat(),
            "status": "validation_failed",
            "mapping": mapping_info,
            "validation": validation,
        }

    scored = score_invoices(canonical, as_of)
    metrics = portfolio_metrics(scored)
    audit = {
        "engine_version": ENGINE_VERSION,
        "as_of": as_of.isoformat(),
        "status": "needs_review",
        "source_file": Path(path).name,
        "mapping": mapping_info,
        "validation": validation,
        "metrics": metrics,
        "top_opportunities": top_opportunities(scored, 10),
        "blockers": blocker_summary(scored),
        "ageing": {
            bucket: {
                "amount": round(float(scored.loc[scored["age_bucket"] == bucket, "outstanding_amount"].sum()), 2),
                "invoice_count": int((scored["age_bucket"] == bucket).sum()),
            }
            for bucket in ["Current","1-30","31-60","61-90","90+"]
        },
        "review_notes": [
            "All calculations are deterministic and should reconcile to the imported ledger.",
            "Multiple currencies are not FX-normalized in v0.1.",
            "AI narrative should be generated only after this structured audit is reviewed.",
        ],
    }
    return audit


def write_scored_csv(input_path: str | Path, audit_path: Path, as_of: date, mapping: Optional[Dict[str,str]]=None):
    raw = read_input(input_path)
    canonical, _ = canonicalize(raw, mapping)
    scored = score_invoices(canonical, as_of)
    out = audit_path.with_name(audit_path.stem + "_scored_invoices.csv")
    scored.to_csv(out, index=False)
    return out


def main():
    parser = argparse.ArgumentParser(description="CollectIQ AR Audit Engine v0.1")
    parser.add_argument("input", help="CSV/XLSX/XLS ageing file")
    parser.add_argument("--as-of", help="Audit date YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--output", default="collectiq_audit.json", help="Output JSON file")
    parser.add_argument("--mapping", help="Optional JSON file mapping canonical names to source columns")
    parser.add_argument("--write-scored-csv", action="store_true")
    args = parser.parse_args()

    as_of = datetime.strptime(args.as_of, "%Y-%m-%d").date() if args.as_of else date.today()
    mapping = None
    if args.mapping:
        mapping = json.loads(Path(args.mapping).read_text())

    audit = build_audit(args.input, as_of, mapping)
    output = Path(args.output)
    output.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")

    if args.write_scored_csv and audit.get("status") != "validation_failed":
        write_scored_csv(args.input, output, as_of, mapping)

    print(json.dumps({
        "status": audit.get("status"),
        "output": str(output),
        "metrics": audit.get("metrics"),
        "validation": {
            "errors": audit.get("validation", {}).get("error_count"),
            "warnings": audit.get("validation", {}).get("warning_count"),
        }
    }, indent=2))


if __name__ == "__main__":
    main()
