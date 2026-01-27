# Universal Report System - Pre-Launch Testing Checklist

## 🔴 CRITICAL - Must Pass Before Launch

### 1. Data Accuracy (THE MOST CRITICAL)
- [ ] **Tax calculation accuracy** - All displayed numbers match backend calculations
- [ ] **Savings estimates** - Conservative, defensible, not overstated
- [ ] **Tax bracket display** - Correct 2025 brackets for each filing status
- [ ] **Deduction limits** - SALT cap $10,000, 401k limits, IRA limits all correct
- [ ] **Credit calculations** - Child tax credit, education credits accurate
- [ ] **Effective/Marginal rates** - Calculated correctly

### 2. Data Source Mapping
- [ ] **Chatbot sessions** - All profile fields map correctly
- [ ] **Advisory reports** - Sections extract properly
- [ ] **Lead magnet sessions** - Limited data handled gracefully
- [ ] **Manual entry** - Form data converts accurately
- [ ] **OCR extraction** - Document data maps correctly

### 3. Edge Cases for Data
- [ ] Empty/null values don't break rendering
- [ ] Zero income handled
- [ ] Very high income ($1M+) displays correctly
- [ ] Negative values (losses) display correctly
- [ ] Decimal precision maintained (no rounding errors)
- [ ] Very long taxpayer names truncate properly

---

## 🟠 HIGH PRIORITY - Should Pass

### 4. Visualization Accuracy
- [ ] **Savings gauge needle** - Points to correct percentage
- [ ] **Pie chart** - Slices sum to 100%
- [ ] **Bar charts** - Heights proportional to values
- [ ] **Tax bracket chart** - Correct bracket boundaries
- [ ] **Trend charts** - Data points connected correctly

### 5. Visualization Rendering
- [ ] SVG renders in all modern browsers (Chrome, Firefox, Safari, Edge)
- [ ] SVG animations work (gauge needle sweep)
- [ ] Charts responsive on mobile
- [ ] Charts render in PDF export
- [ ] Colors contrast properly (accessibility)
- [ ] No clipping/overflow on small screens

### 6. Branding/White-Label
- [ ] Logo displays at correct size
- [ ] Logo position (header/footer/watermark) works
- [ ] Custom colors apply to all elements
- [ ] Firm name appears correctly
- [ ] Advisor info displays when provided
- [ ] Default branding works when no profile

### 7. Section Rendering
- [ ] All 13+ sections render correctly
- [ ] Sections hide when data unavailable
- [ ] Tier 1 (teaser) shows only allowed sections
- [ ] Tier 2 (full) shows appropriate sections
- [ ] Tier 3 (complete) shows all sections
- [ ] Blur overlay works on restricted content
- [ ] Page breaks in correct places

---

## 🟡 MEDIUM PRIORITY - Test Thoroughly

### 8. Export Quality
- [ ] HTML standalone (opens without server)
- [ ] HTML email-compatible version works
- [ ] PDF generates without errors
- [ ] PDF includes all charts/visualizations
- [ ] PDF page breaks clean
- [ ] PDF file size reasonable (<5MB)

### 9. API Integration
- [ ] `/api/advisor/universal-report` POST works
- [ ] `/api/advisor/universal-report/{id}/html` GET works
- [ ] `/api/advisor/universal-report/{id}/pdf` GET works
- [ ] `/lead-magnet/universal-report` GET works
- [ ] Error responses are clear and helpful
- [ ] Session not found returns 404
- [ ] Insufficient data returns 400

### 10. Performance
- [ ] Report generation < 3 seconds
- [ ] HTML size < 100KB (excluding images)
- [ ] No memory leaks on repeated generation
- [ ] Concurrent report generation works

---

## 🟢 LOWER PRIORITY - Nice to Have

### 11. Print Quality
- [ ] Print preview looks correct
- [ ] No cut-off content when printed
- [ ] Charts print clearly (not pixelated)
- [ ] Page numbers work

### 12. Accessibility
- [ ] Alt text on all images
- [ ] Color contrast meets WCAG AA
- [ ] Screen reader compatible
- [ ] Keyboard navigation works

---

## Specific Test Cases

### Tax Scenarios to Test

```
Scenario 1: Simple W-2 Employee
- Filing: Single
- Income: $75,000 W-2
- Deductions: Standard
- Expected: ~$8,500 federal tax, 11.3% effective rate

Scenario 2: Self-Employed
- Filing: Single
- Income: $150,000 business income
- Expected: SE tax shown, QBI deduction mentioned

Scenario 3: High Income Married
- Filing: Married Joint
- Income: $500,000 combined
- Investments: $50,000 capital gains
- Expected: NIIT mentioned, phase-outs noted

Scenario 4: Complex - Multiple Income Sources
- Filing: Head of Household
- W-2: $80,000
- Business: $40,000
- Rental: $20,000 (loss)
- Investments: $15,000
- Expected: All income types shown, PAL rules mentioned

Scenario 5: Minimal Data (Lead Magnet)
- Filing: Single
- Income: $100,000 (only)
- Expected: Teaser report, savings estimate shown
```

### Visualization Tests

```
Test 1: Savings Gauge
Input: Current tax $25,000, Potential savings $5,000
Expected: Needle at 20% savings position, green zone 20%

Test 2: Income Pie Chart
Input: W-2 $100k, Business $50k, Investment $25k
Expected: 3 slices (57%, 29%, 14%), total shows $175k

Test 3: Deduction Comparison
Input: Standard $15,000, Itemized $22,000
Expected: Itemized bar taller, "SELECTED" badge on itemized

Test 4: Tax Bracket Chart
Input: Taxable income $150,000, Single
Expected: 5 bracket segments, 24% bracket highlighted
```

### Branding Tests

```
Test 1: Default Branding
Input: No CPA profile
Expected: Default blue theme, generic firm name

Test 2: Full CPA Branding
Input: Logo URL, custom colors, firm info, advisor info
Expected: All elements display correctly

Test 3: Partial Branding
Input: Only firm name and primary color
Expected: Custom elements shown, defaults for missing
```

---

## Integration Test Scripts

### Python Test Script
```python
# Save as tests/test_universal_report.py

import pytest
from decimal import Decimal
from universal_report import UniversalReportEngine
from universal_report.data_collector import NormalizedReportData, IncomeItem

def test_basic_report_generation():
    """Test basic report generates without errors."""
    engine = UniversalReportEngine()

    session_data = {
        'profile': {
            'filing_status': 'single',
            'total_income': 100000,
        },
        'calculations': {
            'gross_income': 100000,
            'federal_tax': 15000,
            'effective_rate': 15.0,
        },
        'strategies': []
    }

    output = engine.generate_report(
        source_type='chatbot',
        source_data=session_data,
        output_format='html',
    )

    assert output.html_content is not None
    assert len(output.html_content) > 1000
    assert '<!DOCTYPE html>' in output.html_content

def test_savings_gauge_accuracy():
    """Test savings gauge shows correct percentage."""
    from universal_report.visualizations import SavingsGauge

    gauge = SavingsGauge()
    svg = gauge.render(
        current_liability=Decimal('25000'),
        potential_savings=Decimal('5000'),
    )

    # 5000/25000 = 20% savings
    assert 'Potential Savings' in svg
    assert '$5,000' in svg or '5,000' in svg

def test_empty_data_handling():
    """Test that empty/null data doesn't break rendering."""
    engine = UniversalReportEngine()

    session_data = {
        'profile': {'filing_status': 'single'},
        'calculations': None,
        'strategies': []
    }

    output = engine.generate_report(
        source_type='chatbot',
        source_data=session_data,
    )

    # Should not raise, should produce minimal report
    assert output.html_content is not None

def test_all_filing_statuses():
    """Test report works for all filing statuses."""
    engine = UniversalReportEngine()

    statuses = ['single', 'married_joint', 'married_separate',
                'head_of_household', 'qualifying_widow']

    for status in statuses:
        session_data = {
            'profile': {'filing_status': status, 'total_income': 100000},
            'calculations': {'federal_tax': 15000},
            'strategies': []
        }

        output = engine.generate_report(
            source_type='chatbot',
            source_data=session_data,
        )

        assert output.html_content is not None
        assert status.replace('_', ' ').title() in output.html_content

def test_branding_application():
    """Test CPA branding applies correctly."""
    engine = UniversalReportEngine()

    cpa_profile = {
        'firm_name': 'Test Tax Firm',
        'primary_color': '#ff0000',
    }

    session_data = {
        'profile': {'filing_status': 'single', 'total_income': 100000},
        'calculations': {},
        'strategies': []
    }

    output = engine.generate_report(
        source_type='chatbot',
        source_data=session_data,
        cpa_profile=cpa_profile,
    )

    assert 'Test Tax Firm' in output.html_content
    assert '#ff0000' in output.html_content

def test_tier_restrictions():
    """Test tier levels restrict content properly."""
    engine = UniversalReportEngine()

    session_data = {
        'profile': {'filing_status': 'single', 'total_income': 100000},
        'calculations': {'federal_tax': 15000},
        'strategies': [{'title': 'Secret Strategy', 'estimated_savings': 1000}]
    }

    # Tier 1 should blur recommendations
    tier1 = engine.generate_report(
        source_type='chatbot',
        source_data=session_data,
        tier_level=1,
    )
    assert 'blur' in tier1.html_content.lower() or 'Upgrade' in tier1.html_content

    # Tier 2 should show recommendations
    tier2 = engine.generate_report(
        source_type='chatbot',
        source_data=session_data,
        tier_level=2,
    )
    assert 'Secret Strategy' in tier2.html_content or 'Optimization' in tier2.html_content
```

### API Test Script
```bash
# Save as tests/test_api.sh

#!/bin/bash

BASE_URL="http://localhost:5000"

echo "Testing Universal Report API..."

# Test 1: Generate report via POST
echo "Test 1: POST /api/advisor/universal-report"
curl -X POST "$BASE_URL/api/advisor/universal-report" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test_123", "tier_level": 2}' \
  -w "\nHTTP Status: %{http_code}\n"

# Test 2: Get HTML report
echo "\nTest 2: GET /api/advisor/universal-report/test_123/html"
curl "$BASE_URL/api/advisor/universal-report/test_123/html" \
  -w "\nHTTP Status: %{http_code}\n" | head -20

# Test 3: Invalid session
echo "\nTest 3: Invalid session should return 404"
curl "$BASE_URL/api/advisor/universal-report/invalid_session/html" \
  -w "\nHTTP Status: %{http_code}\n"

echo "\nAPI tests complete."
```

---

## Pre-Launch Sign-Off

### Stakeholder Approval
- [ ] Tax accuracy reviewed by CPA
- [ ] Legal/compliance review of disclaimers
- [ ] UX review of report layout
- [ ] Product owner sign-off

### Documentation
- [ ] API documentation complete
- [ ] User guide for CPA branding
- [ ] Troubleshooting guide
- [ ] Known limitations documented

### Monitoring
- [ ] Error logging configured
- [ ] Performance monitoring in place
- [ ] Alerts for generation failures
