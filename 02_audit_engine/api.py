from datetime import date
from pathlib import Path
import tempfile
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from collectiq_engine import build_audit

app = FastAPI(title="CollectIQ Audit Engine", version="0.1.0")

@app.get("/health")
def health():
    return {"ok": True, "service": "collectiq-audit-engine", "version": "0.1.0"}

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
        return result
    finally:
        tmp_path.unlink(missing_ok=True)
