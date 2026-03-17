# Advisory Report Dashboard — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a polished report summary dashboard where CPAs and taxpayers preview key tax metrics and download a comprehensive advisory report PDF.

**Architecture:** A new Jinja2 template page (`advisory_report_dashboard.html`) served by a FastAPI route that generates advisory report data via `AdvisoryReportGenerator`, renders metric cards and recommendation highlights, and provides a download button that hits the existing PDF generation endpoint. Extends `cpa/base.html` for CPA context or `base_modern.html` for client portal.

**Tech Stack:** FastAPI, Jinja2, Alpine.js, custom CSS design system (Navy+Gold), ReportLab PDF (existing pipeline)

---

### Task 1: Create the Report Dashboard Route

**Files:**
- Modify: `src/web/advisor/report_routes.py` (add new template route)

**Step 1: Add the template route to report_routes.py**

Add a new GET endpoint that loads session data, runs the advisory report generator, and renders the dashboard template. Add this after the existing PDF endpoints (around line 287):

```python
@_report_router.get("/report-preview/{session_id}")
async def report_preview_dashboard(
    session_id: str,
    cpa_id: Optional[str] = None,
    _session: str = Depends(verify_session_token),
):
    """Render the advisory report preview dashboard page."""
    from fastapi.responses import HTMLResponse
    from fastapi.templating import Jinja2Templates
    from starlette.requests import Request

    chat_engine = _get_chat_engine()

    # Load session
    session = chat_engine.sessions.get(session_id)
    if not session:
        session = await chat_engine.get_or_create_session(session_id)

    profile = session.get("profile", {})
    if not profile.get("filing_status") or not profile.get("total_income"):
        raise HTTPException(status_code=400, detail="Insufficient data for report preview.")

    # Generate report data
    from web.intelligent_advisor_api import build_tax_return_from_profile
    from advisory.report_generator import AdvisoryReportGenerator, ReportType

    tax_return = build_tax_return_from_profile(profile)
    generator = AdvisoryReportGenerator()
    report = generator.generate_report(
        tax_return=tax_return,
        report_type=ReportType.FULL_ANALYSIS,
        include_entity_comparison=profile.get("is_self_employed", False),
        include_multi_year=True,
        years_ahead=3,
    )

    # Build template context
    report_data = report.to_dict()

    # Extract tax position from current_position section
    tax_position = {}
    for section in report.sections:
        if section.section_id == "current_position":
            tax_position = section.content
        elif section.section_id == "executive_summary":
            tax_position.update(section.content.get("current_liability", {}))

    # Extract top recommendations
    top_recs = []
    for section in report.sections:
        if section.section_id == "recommendations":
            top_recs = section.content.get("top_recommendations", [])[:5]

    # Sections index for the "what's in the full report" checklist
    sections_index = [
        {"id": s.section_id, "title": s.title}
        for s in report.sections
    ]

    # CPA branding context
    cpa_brand = None
    if cpa_id:
        try:
            from web.intelligent_advisor_api import CPA_BRANDING_HELPER_AVAILABLE, create_pdf_brand_config
            if CPA_BRANDING_HELPER_AVAILABLE:
                cpa_brand = create_pdf_brand_config(cpa_id)
        except ImportError:
            pass

    context = {
        "session_id": session_id,
        "taxpayer_name": report.taxpayer_name,
        "tax_year": report.tax_year,
        "filing_status": report.filing_status,
        "generated_at": report.generated_at,
        # Key metrics
        "total_tax_liability": float(report.current_tax_liability),
        "potential_savings": float(report.potential_savings),
        "confidence_score": float(report.confidence_score),
        "recommendations_count": report.top_recommendations_count,
        # Tax position
        "tax_position": tax_position,
        # Top recommendations
        "top_recommendations": top_recs,
        # Sections index
        "sections_index": sections_index,
        # Branding
        "cpa_id": cpa_id,
        "cpa_brand": cpa_brand,
        # Effective rate
        "effective_rate": tax_position.get("effective_rate", 0),
    }

    return context
```

Note: This returns a dict — we'll wire it to the template in Task 2. The route needs the `Request` object for Jinja2. We'll refine this to use `TemplateResponse` once the template exists.

**Step 2: Verify the route registers**

Run: `python -c "from web.advisor.report_routes import _report_router; print([r.path for r in _report_router.routes])"`
Expected: Should include `/report-preview/{session_id}`

**Step 3: Commit**

```bash
git add src/web/advisor/report_routes.py
git commit -m "feat: add advisory report preview dashboard route"
```

---

### Task 2: Create the Dashboard Template

**Files:**
- Create: `src/web/templates/advisory_report_dashboard.html`

**Step 1: Create the dashboard template**

This template extends the standalone advisory report style (similar to `advisory_report_preview.html`). It renders:
1. Header with taxpayer name, tax year, generation date
2. 4 metric cards (Total Tax Liability, Potential Savings, Effective Rate, Recommendations)
3. Top recommendations list (up to 5)
4. Tax position summary table
5. Sections index checklist
6. Sticky download action bar

The template uses Alpine.js for the download flow and matches the existing design system (Navy+Gold, DM Sans/DM Serif Display).

```html
{% from 'macros/icons.html' import icon %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Advisory Report - {{ taxpayer_name }}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/static/css/core/variables.css">
    <link rel="stylesheet" href="/static/css/core/reset.css">
    <link rel="stylesheet" href="/static/css/core/typography.css">
    <link rel="stylesheet" href="/static/css/unified-theme.css">
    <link rel="stylesheet" href="/static/css/pages/report-dashboard.css">
    <script defer src="/static/js/vendor/alpine.min.js"></script>
</head>
<body>
  <div class="report-dashboard" x-data="reportDashboard()">
    <!-- Header -->
    <header class="dashboard-header">
      {% if cpa_brand %}
      <div class="cpa-branding">
        <span class="firm-name">{{ cpa_brand.firm_name }}</span>
      </div>
      {% endif %}
      <div class="header-content">
        <h1 class="taxpayer-name">{{ taxpayer_name }}</h1>
        <div class="header-meta">
          <span class="meta-item">Tax Year {{ tax_year }}</span>
          <span class="meta-divider">·</span>
          <span class="meta-item">{{ filing_status | replace('_', ' ') | title }}</span>
          <span class="meta-divider">·</span>
          <span class="meta-item">Generated {{ generated_at[:10] }}</span>
        </div>
      </div>
    </header>

    <!-- Metric Cards -->
    <section class="metrics-grid">
      <div class="metric-card">
        <div class="metric-label">Total Tax Liability</div>
        <div class="metric-value">${{ "{:,.0f}".format(total_tax_liability) }}</div>
        <div class="metric-sub">Federal + State Combined</div>
      </div>
      <div class="metric-card accent">
        <div class="metric-label">Potential Savings</div>
        <div class="metric-value savings">${{ "{:,.0f}".format(potential_savings) }}</div>
        <div class="metric-sub">Identified Opportunities</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Effective Tax Rate</div>
        <div class="metric-value">{{ "{:.1f}".format(effective_rate) }}%</div>
        <div class="metric-sub">Total Tax / AGI</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">Recommendations</div>
        <div class="metric-value">{{ recommendations_count }}</div>
        <div class="metric-sub">Strategies Found</div>
      </div>
    </section>

    <!-- Top Recommendations -->
    {% if top_recommendations %}
    <section class="section-card">
      <h2 class="section-title">Top Recommendations</h2>
      <div class="recommendations-list">
        {% for rec in top_recommendations %}
        <div class="rec-item">
          <div class="rec-header">
            <span class="rec-priority priority-{{ rec.priority }}">{{ rec.priority | replace('_', ' ') | title }}</span>
            <span class="rec-savings">${{ "{:,.0f}".format(rec.savings) }}</span>
          </div>
          <div class="rec-title">{{ rec.title }}</div>
          <div class="rec-description">{{ rec.description[:120] }}{% if rec.description|length > 120 %}...{% endif %}</div>
        </div>
        {% endfor %}
      </div>
    </section>
    {% endif %}

    <!-- Tax Position Summary -->
    <section class="section-card">
      <h2 class="section-title">Tax Position Summary</h2>
      <table class="position-table">
        <tbody>
          {% if tax_position.get('income_summary') %}
          <tr>
            <td>Adjusted Gross Income (AGI)</td>
            <td class="amount">${{ "{:,.2f}".format(tax_position.income_summary.agi or 0) }}</td>
          </tr>
          <tr>
            <td>Taxable Income</td>
            <td class="amount">${{ "{:,.2f}".format(tax_position.income_summary.taxable_income or 0) }}</td>
          </tr>
          {% endif %}
          {% if tax_position.get('tax_liability') %}
          <tr>
            <td>Federal Tax</td>
            <td class="amount">${{ "{:,.2f}".format(tax_position.tax_liability.federal_tax or 0) }}</td>
          </tr>
          <tr>
            <td>State Tax</td>
            <td class="amount">${{ "{:,.2f}".format(tax_position.tax_liability.state_tax or 0) }}</td>
          </tr>
          <tr class="total-row">
            <td><strong>Total Tax Liability</strong></td>
            <td class="amount"><strong>${{ "{:,.2f}".format(tax_position.tax_liability.total_tax or 0) }}</strong></td>
          </tr>
          {% endif %}
        </tbody>
      </table>
    </section>

    <!-- Full Report Contents -->
    <section class="section-card">
      <h2 class="section-title">Full Report Contents</h2>
      <p class="section-subtitle">The downloadable PDF includes all of the following sections:</p>
      <div class="contents-grid">
        {% for section in sections_index %}
        <div class="content-item">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--color-success-500)" stroke-width="2.5">
            <polyline points="20 6 9 17 4 12"></polyline>
          </svg>
          <span>{{ section.title }}</span>
        </div>
        {% endfor %}
      </div>
    </section>

    <!-- Sticky Action Bar -->
    <div class="action-bar">
      <div class="action-bar-inner">
        <div class="action-info">
          <span class="action-label">Ready to download</span>
          <span class="action-detail">{{ sections_index | length }} sections · {{ recommendations_count }} recommendations</span>
        </div>
        <div class="action-buttons">
          <button class="btn btn-secondary" onclick="window.print()">
            Print Preview
          </button>
          <button class="btn btn-primary" @click="downloadPdf()" :disabled="downloading">
            <template x-if="!downloading">
              <span>Download Full Report (PDF)</span>
            </template>
            <template x-if="downloading">
              <span>Generating PDF...</span>
            </template>
          </button>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <div x-show="toast" x-transition class="toast" :class="toastType" x-text="toastMessage"></div>
  </div>

  <script>
  function reportDashboard() {
    return {
      downloading: false,
      toast: false,
      toastMessage: '',
      toastType: '',

      async downloadPdf() {
        this.downloading = true;
        try {
          const sessionId = '{{ session_id }}';
          const cpaId = '{{ cpa_id or "" }}';
          let url = `/api/advisor/report/${sessionId}/pdf`;
          if (cpaId) {
            url += `?cpa_id=${encodeURIComponent(cpaId)}`;
          }

          const response = await fetch(url, {
            headers: {
              'Authorization': `Bearer ${document.cookie.match(/session_token=([^;]+)/)?.[1] || ''}`,
            }
          });

          if (!response.ok) {
            throw new Error(`PDF generation failed: ${response.status}`);
          }

          const blob = await response.blob();
          const downloadUrl = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = downloadUrl;
          a.download = `tax_advisory_report_${sessionId}.pdf`;
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(downloadUrl);

          this.showToast('Report downloaded successfully', 'success');
        } catch (error) {
          console.error('PDF download error:', error);
          this.showToast('Failed to generate PDF. Please try again.', 'error');
        } finally {
          this.downloading = false;
        }
      },

      showToast(message, type) {
        this.toastMessage = message;
        this.toastType = type;
        this.toast = true;
        setTimeout(() => { this.toast = false; }, 4000);
      }
    };
  }
  </script>
</body>
</html>
```

**Step 2: Verify template renders without errors**

Open browser to `/advisor/report-preview/{session_id}` and verify the page loads.

**Step 3: Commit**

```bash
git add src/web/templates/advisory_report_dashboard.html
git commit -m "feat: add advisory report preview dashboard template"
```

---

### Task 3: Create the Dashboard CSS

**Files:**
- Create: `src/web/static/css/pages/report-dashboard.css`

**Step 1: Create the stylesheet**

Professional styling matching the Navy+Gold design system. Metric cards with DM Serif Display for big numbers, clean table styling, sticky action bar at bottom.

```css
/* Report Dashboard — Advisory Report Preview */

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: var(--font-sans, 'DM Sans', -apple-system, sans-serif);
  background: var(--color-gray-50, #FAF8F4);
  color: var(--color-gray-900, #111827);
  line-height: 1.6;
  padding-bottom: 100px; /* space for sticky bar */
}

.report-dashboard {
  max-width: 960px;
  margin: 0 auto;
  padding: var(--space-6, 24px);
}

/* Header */
.dashboard-header {
  background: linear-gradient(135deg, var(--color-primary-800, #0B1D3A), var(--color-primary-600, #132B50));
  color: white;
  padding: var(--space-8, 32px) var(--space-8, 32px);
  border-radius: var(--radius-xl, 16px);
  margin-bottom: var(--space-6, 24px);
}

.cpa-branding {
  margin-bottom: var(--space-4, 16px);
  padding-bottom: var(--space-3, 12px);
  border-bottom: 1px solid rgba(255,255,255,0.15);
}

.firm-name {
  font-size: var(--text-sm, 14px);
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  opacity: 0.85;
}

.taxpayer-name {
  font-family: var(--font-serif, 'DM Serif Display', Georgia, serif);
  font-size: 32px;
  font-weight: 400;
  margin-bottom: var(--space-2, 8px);
  color: white;
}

.header-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2, 8px);
  font-size: var(--text-sm, 14px);
  opacity: 0.8;
}

.meta-divider { opacity: 0.4; }

/* Metric Cards */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-4, 16px);
  margin-bottom: var(--space-6, 24px);
}

.metric-card {
  background: white;
  border-radius: var(--radius-lg, 12px);
  padding: var(--space-5, 20px);
  box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  border: 1px solid var(--color-gray-200, #e5e7eb);
  transition: box-shadow 0.2s;
}

.metric-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}

.metric-card.accent {
  background: linear-gradient(135deg, var(--color-success-50, #ecfdf5), white);
  border-color: var(--color-success-500, #10b981);
}

.metric-label {
  font-size: var(--text-xs, 12px);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-gray-500, #5b6370);
  margin-bottom: var(--space-1, 4px);
}

.metric-value {
  font-family: var(--font-serif, 'DM Serif Display', Georgia, serif);
  font-size: 28px;
  font-weight: 400;
  color: var(--color-primary-800, #0B1D3A);
  line-height: 1.2;
}

.metric-value.savings {
  color: var(--color-success-600, #059669);
}

.metric-sub {
  font-size: var(--text-xs, 12px);
  color: var(--color-gray-400, #737d8c);
  margin-top: var(--space-1, 4px);
}

/* Section Cards */
.section-card {
  background: white;
  border-radius: var(--radius-lg, 12px);
  padding: var(--space-6, 24px);
  margin-bottom: var(--space-5, 20px);
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
  border: 1px solid var(--color-gray-200, #e5e7eb);
}

.section-title {
  font-family: var(--font-serif, 'DM Serif Display', Georgia, serif);
  font-size: 20px;
  font-weight: 400;
  color: var(--color-primary-800, #0B1D3A);
  margin-bottom: var(--space-4, 16px);
}

.section-subtitle {
  font-size: var(--text-sm, 14px);
  color: var(--color-gray-500, #5b6370);
  margin-bottom: var(--space-4, 16px);
}

/* Recommendations */
.recommendations-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3, 12px);
}

.rec-item {
  padding: var(--space-4, 16px);
  border: 1px solid var(--color-gray-200, #e5e7eb);
  border-radius: var(--radius-md, 8px);
  transition: border-color 0.2s;
}

.rec-item:hover {
  border-color: var(--color-primary-300, #7A9AC4);
}

.rec-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-2, 8px);
}

.rec-priority {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 2px 10px;
  border-radius: 999px;
  background: var(--color-gray-100, #F0EDE6);
  color: var(--color-gray-600, #4b5563);
}

.rec-priority.priority-immediate {
  background: var(--color-error-50, #fef2f2);
  color: var(--color-error-600, #dc2626);
}

.rec-priority.priority-current_year {
  background: var(--color-warning-50, #fffbeb);
  color: var(--color-warning-700, #b45309);
}

.rec-priority.priority-next_year {
  background: var(--color-info-50, #eff6ff);
  color: var(--color-info-500, #3b82f6);
}

.rec-priority.priority-long_term {
  background: var(--color-gray-100, #F0EDE6);
  color: var(--color-gray-600, #4b5563);
}

.rec-savings {
  font-family: var(--font-serif, 'DM Serif Display', Georgia, serif);
  font-size: 18px;
  color: var(--color-success-600, #059669);
  font-weight: 400;
}

.rec-title {
  font-weight: 600;
  font-size: var(--text-base, 16px);
  color: var(--color-gray-900, #111827);
  margin-bottom: var(--space-1, 4px);
}

.rec-description {
  font-size: var(--text-sm, 14px);
  color: var(--color-gray-500, #5b6370);
  line-height: 1.5;
}

/* Tax Position Table */
.position-table {
  width: 100%;
  border-collapse: collapse;
}

.position-table td {
  padding: var(--space-3, 12px) var(--space-2, 8px);
  border-bottom: 1px solid var(--color-gray-100, #F0EDE6);
  font-size: var(--text-sm, 14px);
}

.position-table .amount {
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-weight: 500;
}

.position-table .total-row td {
  border-top: 2px solid var(--color-primary-800, #0B1D3A);
  border-bottom: none;
  padding-top: var(--space-4, 16px);
}

/* Contents Grid */
.contents-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-3, 12px);
}

.content-item {
  display: flex;
  align-items: center;
  gap: var(--space-2, 8px);
  font-size: var(--text-sm, 14px);
  color: var(--color-gray-700, #374151);
}

/* Sticky Action Bar */
.action-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: white;
  border-top: 1px solid var(--color-gray-200, #e5e7eb);
  box-shadow: 0 -4px 16px rgba(0,0,0,0.08);
  z-index: 50;
  padding: var(--space-4, 16px) var(--space-6, 24px);
}

.action-bar-inner {
  max-width: 960px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.action-info { display: flex; flex-direction: column; }

.action-label {
  font-weight: 600;
  font-size: var(--text-sm, 14px);
  color: var(--color-gray-900, #111827);
}

.action-detail {
  font-size: var(--text-xs, 12px);
  color: var(--color-gray-500, #5b6370);
}

.action-buttons {
  display: flex;
  gap: var(--space-3, 12px);
}

.btn {
  padding: var(--space-2, 8px) var(--space-5, 20px);
  border-radius: var(--radius-md, 8px);
  font-weight: 600;
  font-size: var(--text-sm, 14px);
  border: none;
  cursor: pointer;
  transition: all 0.15s;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  background: linear-gradient(135deg, var(--color-primary-600, #132B50), var(--color-primary-800, #0B1D3A));
  color: white;
}

.btn-primary:hover:not(:disabled) {
  box-shadow: 0 4px 12px rgba(11,29,58,0.3);
  transform: translateY(-1px);
}

.btn-secondary {
  background: white;
  color: var(--color-gray-700, #374151);
  border: 1px solid var(--color-gray-300, #d1d5db);
}

.btn-secondary:hover {
  background: var(--color-gray-50, #FAF8F4);
}

/* Toast */
.toast {
  position: fixed;
  bottom: 100px;
  left: 50%;
  transform: translateX(-50%);
  padding: var(--space-3, 12px) var(--space-5, 20px);
  border-radius: var(--radius-md, 8px);
  font-size: var(--text-sm, 14px);
  font-weight: 500;
  z-index: 60;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

.toast.success {
  background: var(--color-success-600, #059669);
  color: white;
}

.toast.error {
  background: var(--color-error-600, #dc2626);
  color: white;
}

/* Responsive */
@media (max-width: 768px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .contents-grid {
    grid-template-columns: 1fr;
  }

  .action-bar-inner {
    flex-direction: column;
    gap: var(--space-3, 12px);
  }

  .action-buttons {
    width: 100%;
  }

  .action-buttons .btn {
    flex: 1;
  }

  .taxpayer-name {
    font-size: 24px;
  }

  .metric-value {
    font-size: 22px;
  }
}

@media (max-width: 480px) {
  .metrics-grid {
    grid-template-columns: 1fr;
  }
}

/* Print */
@media print {
  .action-bar { display: none; }
  .toast { display: none; }
  body { padding-bottom: 0; }

  .report-dashboard {
    max-width: 100%;
    padding: 0;
  }
}
```

**Step 2: Commit**

```bash
git add src/web/static/css/pages/report-dashboard.css
git commit -m "feat: add report dashboard CSS with metric cards and sticky action bar"
```

---

### Task 4: Wire Route to Template with TemplateResponse

**Files:**
- Modify: `src/web/advisor/report_routes.py` (refine route to use TemplateResponse)

**Step 1: Update the route to return TemplateResponse**

The route from Task 1 needs to accept `Request` and return a `TemplateResponse`. Update the route signature and return:

```python
from fastapi import Request as FastAPIRequest

@_report_router.get("/report-preview/{session_id}")
async def report_preview_dashboard(
    request: FastAPIRequest,
    session_id: str,
    cpa_id: Optional[str] = None,
    _session: str = Depends(verify_session_token),
):
    """Render the advisory report preview dashboard page."""
    from fastapi.templating import Jinja2Templates
    import os

    templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
    templates = Jinja2Templates(directory=templates_dir)

    # ... (same data loading logic as Task 1) ...

    context["request"] = request

    return templates.TemplateResponse("advisory_report_dashboard.html", context)
```

Note: Check if there's a shared `templates` instance in the codebase (likely in `page_routes.py` or the main app). If so, import that instead of creating a new one.

**Step 2: Test the full flow**

1. Start the dev server
2. Navigate to `/api/advisor/report-preview/{session_id}` with a valid session
3. Verify the dashboard renders with correct numbers
4. Click "Download Full Report (PDF)" and verify PDF downloads

**Step 3: Commit**

```bash
git add src/web/advisor/report_routes.py
git commit -m "feat: wire report preview route to template response"
```

---

### Task 5: Add "View Advisory Report" Link from CPA Return Review

**Files:**
- Modify: `src/web/templates/cpa/return_review.html`

**Step 1: Add a "View Advisory Report" button to the CPA return review page**

Find the header section (around line 19-33) and add a button in `header-right` next to the status badge:

```html
<a href="/api/advisor/report-preview/{{ session_id }}{% if cpa %}?cpa_id={{ cpa.id or '' }}{% endif %}"
   class="btn btn-outline" style="margin-right: var(--space-3);">
    View Advisory Report
</a>
```

**Step 2: Verify the link works**

Navigate to a CPA return review page, click "View Advisory Report", confirm it opens the dashboard.

**Step 3: Commit**

```bash
git add src/web/templates/cpa/return_review.html
git commit -m "feat: add View Advisory Report link to CPA return review page"
```

---

### Task 6: End-to-End Verification

**Step 1: Test with CPA context**

1. Navigate to CPA dashboard → Returns → Review a return
2. Click "View Advisory Report"
3. Verify: CPA branding bar shows, all 4 metrics have correct non-zero numbers
4. Verify: Top recommendations list shows with savings amounts
5. Verify: Tax position table has correct AGI/taxable/federal/state
6. Click "Download Full Report (PDF)" → PDF downloads with CPA branding

**Step 2: Test without CPA context**

1. Navigate directly to `/api/advisor/report-preview/{session_id}` (no cpa_id)
2. Verify: No CPA branding bar, neutral styling
3. Verify: Same metrics and data accuracy
4. Download PDF → neutral branding

**Step 3: Test responsiveness**

1. Resize browser to mobile width
2. Verify: Metric cards stack to 2-column then 1-column
3. Verify: Action bar buttons stack vertically
4. Verify: Print Preview (Cmd+P) hides action bar

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: advisory report dashboard — preview and download experience"
```
