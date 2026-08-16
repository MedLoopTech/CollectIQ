# CollectIQ v0.3 Architecture

```text
                     ┌──────────────────────────┐
                     │  APIFY HIRING SIGNALS    │
                     │ LinkedIn / Indeed / Jobs │
                     └─────────────┬────────────┘
                                   │
                                   ▼
                         n8n Lead Generator
                                   │
                                   ▼
                         Supabase Prospects
                                   │
                                   ▼
                         Human Review / Outreach
                                   │
                                   ▼
                         Free AR Audit Offer
                                   │
                                   ▼
┌────────────────┐       ┌───────────────────┐
│ Landing Page   │──────▶│ Secure AR Upload  │
│ + Intake Form  │       │ Supabase Storage  │
└────────────────┘       └─────────┬─────────┘
                                   │
                                   ▼
                           n8n Intake Flow
                                   │
                                   ▼
                         CollectIQ Audit Engine
                         Python / FastAPI
                                   │
                                   ▼
                         Structured Audit JSON
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
             Supabase Audit DB             Report Renderer
                    │                             │
                    ▼                             ▼
             Reviewer Dashboard             HTML / PDF
                    │                             │
                    └──────────────┬──────────────┘
                                   ▼
                              Human Approval
                                   │
                                   ▼
                              Send Audit
                                   │
                                   ▼
                        30-Day Recovery Sprint
```
