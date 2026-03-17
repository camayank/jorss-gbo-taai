# Tax Advisory Report — Summary Preview & Download

**Date**: 2026-03-06
**Status**: Approved

## Problem

The Tax Advisory Report needs a polished preview screen where CPAs and taxpayers can review key metrics at a glance, verify numbers are correct, and download the full comprehensive PDF report.

## Requirements

- **Audience**: Both CPA (from CPA dashboard) and taxpayer (from client portal)
- **Preview UX**: Summary dashboard with key metrics + "Download Full Report (PDF)" button
- **PDF branding**: Dynamic — CPA-branded when accessed with cpa_id param, neutral otherwise
- **Numbers accuracy**: Single source of truth via AdvisoryReportGenerator → FederalTaxEngine

## Design

### Page Layout

```
┌──────────────────────────────────────────────────────────┐
│  HEADER: Taxpayer name, tax year, generation timestamp   │
│  CPA branding bar (logo + firm name, if applicable)      │
├──────────────────────────────────────────────────────────┤
│  METRIC CARDS ROW (4 cards):                             │
│  [Total Tax Liability] [Potential Savings]               │
│  [Effective Tax Rate]  [Recommendations Found]           │
├──────────────────────────────────────────────────────────┤
│  TOP 3 RECOMMENDATIONS                                   │
│  Card per recommendation with priority badge, title,     │
│  estimated savings amount                                │
├──────────────────────────────────────────────────────────┤
│  TAX POSITION SUMMARY TABLE                              │
│  AGI / Taxable Income / Federal Tax / State Tax          │
├──────────────────────────────────────────────────────────┤
│  FULL REPORT CONTENTS INDEX                              │
│  Checklist of sections included in the downloadable PDF  │
├──────────────────────────────────────────────────────────┤
│  STICKY ACTION BAR                                       │
│  [Download Full Report (PDF)]  [Print Preview]           │
└──────────────────────────────────────────────────────────┘
```

### Data Flow

1. User clicks "View Report" from CPA dashboard or client portal
2. `GET /advisor/report-preview/{session_id}?cpa_id=...` loads the page
3. Server runs `AdvisoryReportGenerator.generate_report()` → returns `AdvisoryReportResult`
4. Template renders summary dashboard with Alpine.js for interactivity
5. User clicks "Download Full Report (PDF)"
6. `GET /api/advisor/report/{session_id}/pdf?cpa_id=...` (existing endpoint)
7. Browser auto-downloads the PDF

### Branding Logic

- If `cpa_id` query param present → load CPA profile → apply `CPABrandConfig` to both preview and PDF
- If absent → neutral Jorss styling (navy + gold design system)
- PDF inherits same branding via existing `export_advisory_report_to_pdf()` pipeline

### Files

| File | Action | Purpose |
|------|--------|---------|
| `src/web/templates/advisory_report_dashboard.html` | Create | Summary preview page template |
| `src/web/static/js/pages/report-dashboard.js` | Create | Alpine.js controller (download flow, loading states) |
| `src/web/static/css/pages/report-dashboard.css` | Create | Page-specific styles (metric cards, section index) |
| `src/web/advisor/report_routes.py` | Modify | Add GET /advisor/report-preview/{session_id} template route |
| `src/web/templates/cpa/return_review.html` | Modify | Add "View Report Dashboard" link |

### Tech Stack

- **Template**: Jinja2 extending base_modern.html
- **Interactivity**: Alpine.js (consistent with rest of app)
- **Styling**: Custom CSS using existing design system variables (--color-primary-*, --color-accent-*, DM Sans/DM Serif Display)
- **PDF generation**: Existing ReportLab pipeline via advisory_pdf_exporter.py
- **Data source**: AdvisoryReportGenerator → FederalTaxEngine (single source of truth for numbers)
