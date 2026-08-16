# CollectIQ Report Renderer v0.1

Customer-facing report layer for the AR Audit Engine.

Included:
- `northstar_ar_intelligence_audit.html` - responsive web report
- `northstar_ar_intelligence_audit.pdf` - client-ready 2-page PDF
- `render_report.py` - starter generic renderer integration script

The sample report is driven from the Northstar audit JSON and demonstrates the approved v0.1 layout:
1. AR Health Score
2. headline AR metrics
3. high-priority collection pool
4. executive summary
5. ageing profile
6. top collection opportunities
7. blocker analysis
8. 30-day recovery workflow
9. interpretation notes and disclaimer

Recommended production flow:
Audit Engine JSON -> internal review -> approved report renderer -> PDF/web report -> prospect.

Do not automatically send unreviewed pilot reports.
