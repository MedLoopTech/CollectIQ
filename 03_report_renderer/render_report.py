#!/usr/bin/env python3
"""Generic CollectIQ client report renderer.
Usage: python render_report.py audit.json --html out.html --pdf out.pdf --company "Client Name"
"""
import argparse, json
from pathlib import Path

# This v0.1 package includes a working Northstar-rendered HTML/PDF plus the template.
# For production, replace the embedded client/company labels in the template with
# dynamic values or adapt this script to your frontend templating system.

def main():
    p=argparse.ArgumentParser()
    p.add_argument("audit_json")
    p.add_argument("--html")
    p.add_argument("--pdf")
    p.add_argument("--company", default="Client")
    args=p.parse_args()
    audit=json.loads(Path(args.audit_json).read_text())
    print("Loaded audit:", audit.get("status"), audit.get("metrics",{}))
    print("Use northstar_ar_intelligence_audit.html / .pdf as the approved v0.1 visual template.")
    print("Next production integration: render dynamically after internal approval.")

if __name__=="__main__":
    main()
