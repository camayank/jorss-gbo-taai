# Complete Pending Tasks List - All Sprints & Phases
## Comprehensive Task Inventory for Tax Advisory Platform

**Date**: 2026-01-21
**Status**: Sprint 1 ✅ COMPLETE | Backend Audit ✅ COMPLETE | Sprint 2 ✅ COMPLETE
**Current Position**: Ready for Sprint 3 or Enhancement Phase

---

## 📊 OVERVIEW

### Completed Work ✅
- **Sprint 1**: 5 issues (100% complete)
- **Backend Audit**: All APIs verified working
- **Sprint 2**: 5 issues (100% complete - just finished)
- **Advisory Report Design**: Complete (4 comprehensive documents created)
- **Unwritten Wisdom Document**: Complete
- **Value Addition Analysis**: 6+ features designed

### Pending Work ⏳
- **Sprint 3**: 5 issues (Medium priority features)
- **Sprint 4**: 5 issues (Polish & advanced features)
- **Enhancement Roadmap**: 10+ major enhancements
- **Advisory Report Implementation**: Full system build
- **Value Addition Features**: 20+ opportunities identified

---

## SPRINT 3: MEDIUM PRIORITY FEATURES ⏳
**Status**: ⬜ PENDING
**Estimated Time**: 8-12 hours (1-2 days)
**Priority**: MEDIUM
**Impact**: Quality-of-life improvements, professional polish

---

### Issue #11: Prior Year Data Import
**Priority**: MEDIUM
**Time**: 2-3 hours
**Impact**: 60% faster filing for returning users

#### What It Does:
- Import last year's return data with one click
- Pre-fill name, address, SSN, dependents
- Carry forward mortgage interest, property tax, etc.
- Highlight what changed year-over-year

#### Files to Create:
- `src/import/prior_year_importer.py` (import logic)

#### Files to Modify:
- `src/web/app.py` (add `/api/import-prior-year` route)
- `src/database/session_persistence.py` (query prior year sessions)
- `src/web/templates/index.html` (add "Import Last Year" button)

#### Implementation Steps:
```python
# src/import/prior_year_importer.py

class PriorYearImporter:
    """
    Import data from prior year return to pre-fill current year.
    """

    def import_from_prior_year(
        self,
        user_id: str,
        current_year: int,
        prior_year: int
    ) -> ImportResult:
        """
        Import applicable data from prior year.

        Imports:
        - Personal info (name, SSN, address)
        - Dependents
        - Filing status (if unchanged)
        - Recurring deductions (mortgage, property tax)
        - Bank account for refund

        Does NOT import:
        - Income (changes every year)
        - Withholding (changes every year)
        - Most deductions (need fresh receipts)
        """

        prior_session = self.get_session(user_id, prior_year)
        if not prior_session:
            return ImportResult(success=False, error="No prior year found")

        imported_data = {
            # Personal info
            "name": prior_session.user_name,
            "ssn": prior_session.user_ssn,
            "address": prior_session.user_address,
            "date_of_birth": prior_session.user_dob,

            # Family
            "filing_status": prior_session.filing_status,
            "dependents": prior_session.dependents,

            # Recurring deductions (flag for user to confirm)
            "recurring_deductions": {
                "mortgage_interest": {
                    "prior_amount": prior_session.extracted_data.get("mortgage_interest"),
                    "needs_confirmation": True
                },
                "property_tax": {
                    "prior_amount": prior_session.extracted_data.get("property_tax"),
                    "needs_confirmation": True
                },
                "student_loan_interest": {
                    "prior_amount": prior_session.extracted_data.get("student_loan_interest"),
                    "needs_confirmation": True
                }
            },

            # Bank account
            "bank_routing": prior_session.bank_routing,
            "bank_account": prior_session.bank_account
        }

        # Identify changes to highlight
        changes_to_review = self._identify_changes(prior_session, imported_data)

        return ImportResult(
            success=True,
            imported_data=imported_data,
            changes_to_review=changes_to_review,
            items_imported=len(imported_data)
        )
```

#### UI Integration:
```html
<!-- Prior year import button -->
<div class="prior-year-import-banner">
  <div class="banner-icon">📋</div>
  <div class="banner-content">
    <h4>Welcome Back!</h4>
    <p>We found your 2024 return. Import your info to save time?</p>
  </div>
  <button class="btn-primary" onclick="importPriorYear()">
    ✨ Import Last Year's Data
  </button>
</div>

<!-- Import confirmation modal -->
<div class="import-modal">
  <h3>📋 Importing from 2024 Return</h3>

  <div class="import-preview">
    <h4>✅ These will be imported:</h4>
    <ul class="import-list">
      <li>✓ Personal info (name, SSN, address)</li>
      <li>✓ 2 dependents</li>
      <li>✓ Married Filing Jointly status</li>
      <li>✓ Bank account for direct deposit</li>
    </ul>

    <h4>⚠️ Please confirm these amounts:</h4>
    <ul class="needs-confirmation">
      <li>
        <span class="item">Mortgage Interest</span>
        <span class="amount">$18,200 (2024)</span>
        <button class="btn-small">Use This</button>
        <button class="btn-small">Update</button>
      </li>
      <li>
        <span class="item">Property Tax</span>
        <span class="amount">$4,200 (2024)</span>
        <button class="btn-small">Use This</button>
        <button class="btn-small">Update</button>
      </li>
    </ul>

    <h4>📄 You'll still need to upload:</h4>
    <ul class="still-needed">
      <li>❌ W-2 forms (income changes every year)</li>
      <li>❌ 1099 forms (if applicable)</li>
      <li>❌ New receipts for deductions</li>
    </ul>
  </div>

  <div class="import-actions">
    <button class="btn-primary" onclick="confirmImport()">Import & Continue</button>
    <button class="btn-secondary" onclick="startFresh()">Start Fresh Instead</button>
  </div>
</div>
```

**Testing Requirements**:
- Test with user who has prior year data
- Test with user who doesn't have prior year data
- Test with user whose situation changed (married, divorced, had baby)
- Verify no income/withholding is imported (must be fresh)

---

### Issue #12: Smart Field Prefill (Address Autocomplete)
**Priority**: MEDIUM
**Time**: 1-2 hours
**Impact**: +15% completion rate, faster data entry

#### What It Does:
- Address autocomplete using Google Places API
- SSN formatting as user types (XXX-XX-XXXX)
- Phone number formatting ((XXX) XXX-XXXX)
- Auto-capitalize names
- Smart date picker with validation

#### Files to Modify:
- `src/web/templates/index.html` (add autocomplete JavaScript)
- `src/web/static/js/smart-input.js` (NEW - input enhancement library)

#### Implementation Steps:
```javascript
// src/web/static/js/smart-input.js

class SmartInputEnhancer {
    /**
     * Enhance form inputs with smart features.
     */

    initAddressAutocomplete(inputElement) {
        // Google Places Autocomplete
        const autocomplete = new google.maps.places.Autocomplete(inputElement, {
            types: ['address'],
            componentRestrictions: { country: 'us' }
        });

        autocomplete.addListener('place_changed', () => {
            const place = autocomplete.getPlace();

            // Auto-fill address fields
            document.getElementById('street').value =
                this.extractAddressComponent(place, 'street_number') + ' ' +
                this.extractAddressComponent(place, 'route');

            document.getElementById('city').value =
                this.extractAddressComponent(place, 'locality');

            document.getElementById('state').value =
                this.extractAddressComponent(place, 'administrative_area_level_1');

            document.getElementById('zip').value =
                this.extractAddressComponent(place, 'postal_code');
        });
    }

    initSSNFormatting(inputElement) {
        inputElement.addEventListener('input', (e) => {
            let value = e.target.value.replace(/\D/g, ''); // Remove non-digits

            if (value.length > 9) {
                value = value.slice(0, 9);
            }

            // Format: XXX-XX-XXXX
            if (value.length > 5) {
                value = value.slice(0, 3) + '-' + value.slice(3, 5) + '-' + value.slice(5);
            } else if (value.length > 3) {
                value = value.slice(0, 3) + '-' + value.slice(3);
            }

            e.target.value = value;
        });
    }

    initPhoneFormatting(inputElement) {
        inputElement.addEventListener('input', (e) => {
            let value = e.target.value.replace(/\D/g, '');

            if (value.length > 10) {
                value = value.slice(0, 10);
            }

            // Format: (XXX) XXX-XXXX
            if (value.length > 6) {
                value = '(' + value.slice(0, 3) + ') ' +
                        value.slice(3, 6) + '-' + value.slice(6);
            } else if (value.length > 3) {
                value = '(' + value.slice(0, 3) + ') ' + value.slice(3);
            } else if (value.length > 0) {
                value = '(' + value;
            }

            e.target.value = value;
        });
    }

    initNameCapitalization(inputElement) {
        inputElement.addEventListener('blur', (e) => {
            // Auto-capitalize names properly
            const words = e.target.value.toLowerCase().split(' ');
            const capitalized = words.map(word => {
                if (word.length === 0) return word;

                // Special cases
                if (word === 'van' || word === 'de' || word === 'von') {
                    return word; // Don't capitalize these
                }

                // Handle hyphenated names
                if (word.includes('-')) {
                    return word.split('-').map(part =>
                        part.charAt(0).toUpperCase() + part.slice(1)
                    ).join('-');
                }

                // Handle names with apostrophes (O'Brien, D'Angelo)
                if (word.includes("'")) {
                    const parts = word.split("'");
                    return parts[0].charAt(0).toUpperCase() + parts[0].slice(1) +
                           "'" + parts[1].charAt(0).toUpperCase() + parts[1].slice(1);
                }

                return word.charAt(0).toUpperCase() + word.slice(1);
            });

            e.target.value = capitalized.join(' ');
        });
    }

    initSmartDatePicker(inputElement) {
        // Use a date picker library like flatpickr
        flatpickr(inputElement, {
            dateFormat: 'm/d/Y',
            maxDate: 'today',
            minDate: new Date(1900, 0, 1),
            onChange: (selectedDates, dateStr) => {
                // Validate age if SSN field
                const age = this.calculateAge(selectedDates[0]);
                if (age < 18) {
                    inputElement.classList.add('warning');
                    this.showTooltip(inputElement, 'Are you filing for a minor?');
                }
            }
        });
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    const enhancer = new SmartInputEnhancer();

    // Enhance all address inputs
    enhancer.initAddressAutocomplete(document.getElementById('address'));

    // Enhance SSN inputs
    document.querySelectorAll('input[data-type="ssn"]').forEach(input => {
        enhancer.initSSNFormatting(input);
    });

    // Enhance phone inputs
    document.querySelectorAll('input[data-type="phone"]').forEach(input => {
        enhancer.initPhoneFormatting(input);
    });

    // Enhance name inputs
    document.querySelectorAll('input[data-type="name"]').forEach(input => {
        enhancer.initNameCapitalization(input);
    });

    // Enhance date inputs
    document.querySelectorAll('input[data-type="date"]').forEach(input => {
        enhancer.initSmartDatePicker(input);
    });
});
```

**Dependencies**:
```bash
# Add to requirements or load from CDN
- Google Places API key
- flatpickr (date picker library)
```

**Testing Requirements**:
- Test address autocomplete with various addresses
- Test SSN formatting (handles paste, backspace)
- Test phone formatting
- Test name capitalization edge cases (O'Brien, van der Berg, Mary-Kate)

---

### Issue #13: Contextual Help Tooltips
**Priority**: MEDIUM
**Time**: 2 hours
**Impact**: -30% support requests, +20% user confidence

#### What It Does:
- Hover tooltips explaining every field
- "Why does this matter?" explanations
- Example values for clarity
- Links to IRS publications for detail

#### Files to Create:
- `src/web/static/js/contextual-help.js` (tooltip system)
- `src/web/static/css/tooltips.css` (tooltip styling)
- `src/data/help_content.json` (all help text)

#### Implementation:
```javascript
// src/web/static/js/contextual-help.js

const HELP_CONTENT = {
    "ssn": {
        "title": "Social Security Number",
        "explanation": "Your 9-digit SSN from your Social Security card. We need this to file your return.",
        "why_matters": "The IRS uses your SSN to match your return to your records.",
        "example": "123-45-6789",
        "common_mistakes": [
            "Using your spouse's SSN by accident",
            "Transposing numbers",
            "Using EIN (business tax ID) instead"
        ],
        "irs_reference": "https://www.irs.gov/faqs/irs-procedures/..."
    },

    "filing_status": {
        "title": "Filing Status",
        "explanation": "Your marital status on December 31 determines how you file.",
        "why_matters": "Filing status affects your tax brackets, standard deduction, and available credits. It can change your tax by thousands of dollars.",
        "options": [
            {
                "value": "single",
                "label": "Single",
                "when_to_use": "You were unmarried on Dec 31",
                "standard_deduction": "$14,600 (2025)"
            },
            {
                "value": "married_filing_jointly",
                "label": "Married Filing Jointly",
                "when_to_use": "You were married on Dec 31 and filing together",
                "standard_deduction": "$29,200 (2025)",
                "tip": "Usually saves the most taxes for married couples"
            },
            {
                "value": "head_of_household",
                "label": "Head of Household",
                "when_to_use": "You're unmarried AND paid over half the cost of keeping up a home for a qualifying person",
                "standard_deduction": "$21,900 (2025)",
                "tip": "Better rates than Single, but you must qualify"
            }
        ]
    },

    "wages": {
        "title": "Wages (W-2 Box 1)",
        "explanation": "Total income from your job, including salary, bonuses, and tips.",
        "why_matters": "This is the main number the IRS uses to calculate your taxes.",
        "where_to_find": "W-2 form, Box 1 (NOT Box 5 - that's higher due to pre-tax deductions)",
        "example": "$85,000",
        "common_mistakes": [
            "Using Box 5 instead of Box 1 (Box 5 includes 401k contributions)",
            "Forgetting to include bonuses",
            "Not combining multiple W-2s"
        ],
        "pro_tip": "Box 1 is LOWER than Box 5 if you contribute to 401(k) or HSA - that's good!"
    },

    "mortgage_interest": {
        "title": "Mortgage Interest Paid",
        "explanation": "Interest you paid on your home mortgage loan.",
        "why_matters": "Mortgage interest is deductible if you itemize. Can save $1,000-$5,000 in taxes.",
        "where_to_find": "Form 1098 from your mortgage lender (arrives in January)",
        "example": "$18,200",
        "when_deductible": "Only if you itemize deductions (not if you take standard deduction)",
        "pro_tip": "If you bought your house this year, you can deduct interest starting from your first payment."
    },

    "charitable_contributions": {
        "title": "Charitable Contributions",
        "explanation": "Money or goods you donated to qualified charities.",
        "why_matters": "Reduces your taxable income if you itemize.",
        "requirements": [
            "Must be to IRS-qualified 501(c)(3) organizations",
            "Need written acknowledgment for donations over $250",
            "Need appraisal for non-cash donations over $5,000"
        ],
        "example": "$3,500",
        "what_counts": [
            "Cash donations",
            "Check or credit card payments",
            "Fair market value of donated goods (clothes, furniture)",
            "Mileage driven for charity work (14¢/mile in 2025)"
        ],
        "what_doesnt_count": [
            "Political contributions",
            "Money to individuals (GoFundMe, etc.)",
            "Value of your time/services"
        ]
    },

    "dependents": {
        "title": "Dependents",
        "explanation": "Children or relatives you financially support.",
        "why_matters": "Each dependent can reduce your taxes by $2,000+ through tax credits.",
        "who_qualifies": [
            "Your child under 17 (Child Tax Credit)",
            "Your child 17-24 if full-time student",
            "Elderly parent you support",
            "Other relatives who lived with you and you supported"
        ],
        "requirements": [
            "Lived with you more than half the year",
            "You provided more than half their support",
            "They didn't provide more than half their own support"
        ],
        "pro_tip": "If divorced, usually the parent with custody for more nights claims the child."
    }
};

class ContextualHelpSystem {
    initializeTooltips() {
        // Add help icons to all fields
        document.querySelectorAll('[data-help-key]').forEach(field => {
            const helpKey = field.getAttribute('data-help-key');
            const helpIcon = this.createHelpIcon(helpKey);
            field.parentElement.appendChild(helpIcon);
        });
    }

    createHelpIcon(helpKey) {
        const icon = document.createElement('span');
        icon.className = 'help-icon';
        icon.innerHTML = '?';
        icon.setAttribute('data-help-key', helpKey);

        // Tooltip on hover
        icon.addEventListener('mouseenter', (e) => {
            this.showTooltip(e.target, helpKey);
        });

        icon.addEventListener('mouseleave', () => {
            this.hideTooltip();
        });

        return icon;
    }

    showTooltip(element, helpKey) {
        const content = HELP_CONTENT[helpKey];
        if (!content) return;

        const tooltip = document.createElement('div');
        tooltip.className = 'contextual-tooltip';
        tooltip.innerHTML = this.formatTooltipContent(content);

        // Position near the element
        const rect = element.getBoundingClientRect();
        tooltip.style.left = rect.right + 10 + 'px';
        tooltip.style.top = rect.top + 'px';

        document.body.appendChild(tooltip);

        // Fade in animation
        setTimeout(() => tooltip.classList.add('visible'), 10);
    }

    formatTooltipContent(content) {
        let html = `
            <div class="tooltip-header">
                <h4>${content.title}</h4>
            </div>
            <div class="tooltip-body">
                <p>${content.explanation}</p>
        `;

        if (content.why_matters) {
            html += `
                <div class="why-matters">
                    <strong>Why this matters:</strong>
                    <p>${content.why_matters}</p>
                </div>
            `;
        }

        if (content.example) {
            html += `
                <div class="example">
                    <strong>Example:</strong> ${content.example}
                </div>
            `;
        }

        if (content.where_to_find) {
            html += `
                <div class="where-to-find">
                    <strong>Where to find:</strong>
                    <p>${content.where_to_find}</p>
                </div>
            `;
        }

        if (content.pro_tip) {
            html += `
                <div class="pro-tip">
                    <span class="tip-icon">💡</span>
                    <strong>Pro Tip:</strong> ${content.pro_tip}
                </div>
            `;
        }

        if (content.irs_reference) {
            html += `
                <div class="tooltip-footer">
                    <a href="${content.irs_reference}" target="_blank">
                        📖 IRS Reference
                    </a>
                </div>
            `;
        }

        html += '</div>';
        return html;
    }
}
```

**UI CSS**:
```css
/* src/web/static/css/tooltips.css */

.help-icon {
    display: inline-block;
    width: 18px;
    height: 18px;
    line-height: 18px;
    text-align: center;
    border-radius: 50%;
    background: #3b82f6;
    color: white;
    font-size: 12px;
    font-weight: bold;
    cursor: help;
    margin-left: 6px;
    transition: all 0.2s;
}

.help-icon:hover {
    background: #2563eb;
    transform: scale(1.1);
}

.contextual-tooltip {
    position: fixed;
    max-width: 400px;
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.15);
    padding: 16px;
    z-index: 9999;
    opacity: 0;
    transition: opacity 0.2s;
}

.contextual-tooltip.visible {
    opacity: 1;
}

.tooltip-header h4 {
    margin: 0 0 12px 0;
    color: #1f2937;
    font-size: 16px;
}

.tooltip-body p {
    margin: 0 0 12px 0;
    color: #4b5563;
    font-size: 14px;
    line-height: 1.5;
}

.why-matters {
    background: #eff6ff;
    border-left: 3px solid #3b82f6;
    padding: 10px;
    margin: 12px 0;
}

.example {
    background: #f3f4f6;
    padding: 8px 12px;
    border-radius: 4px;
    font-family: 'Courier New', monospace;
    color: #059669;
}

.pro-tip {
    background: #fef3c7;
    border-left: 3px solid #f59e0b;
    padding: 10px;
    margin: 12px 0;
}

.pro-tip .tip-icon {
    margin-right: 6px;
}
```

---

### Issue #14: Keyboard Shortcuts
**Priority**: LOW-MEDIUM
**Time**: 1-2 hours
**Impact**: Power users love it, +10% efficiency

#### What It Does:
- Tab through form fields smoothly
- Ctrl/Cmd + S to save
- Ctrl/Cmd + Enter to submit
- Arrow keys to navigate steps
- / to focus search
- ? to show help overlay

#### Implementation:
```javascript
// src/web/static/js/keyboard-shortcuts.js

class KeyboardShortcuts {
    constructor() {
        this.shortcuts = {
            'ctrl+s': this.saveProgress,
            'cmd+s': this.saveProgress,
            'ctrl+enter': this.submitForm,
            'cmd+enter': this.submitForm,
            'arrowleft': this.previousStep,
            'arrowright': this.nextStep,
            '/': this.focusSearch,
            '?': this.showShortcutHelp
        };

        this.initialize();
    }

    initialize() {
        document.addEventListener('keydown', (e) => {
            const key = this.getKeyCombo(e);
            const handler = this.shortcuts[key];

            if (handler) {
                e.preventDefault();
                handler.call(this);
            }
        });

        // Show shortcuts hint
        this.showShortcutHint();
    }

    getKeyCombo(e) {
        const parts = [];
        if (e.ctrlKey) parts.push('ctrl');
        if (e.metaKey) parts.push('cmd');
        if (e.shiftKey) parts.push('shift');
        if (e.altKey) parts.push('alt');

        const key = e.key.toLowerCase();
        parts.push(key);

        return parts.join('+');
    }

    saveProgress() {
        console.log('Saving progress...');
        // Trigger auto-save
        if (window.triggerAutoSave) {
            window.triggerAutoSave();
        }
    }

    submitForm() {
        console.log('Submitting form...');
        const submitBtn = document.querySelector('.btn-submit');
        if (submitBtn && !submitBtn.disabled) {
            submitBtn.click();
        }
    }

    previousStep() {
        const backBtn = document.querySelector('.btn-back');
        if (backBtn) backBtn.click();
    }

    nextStep() {
        const nextBtn = document.querySelector('.btn-next');
        if (nextBtn && !nextBtn.disabled) nextBtn.click();
        }
    }

    focusSearch() {
        const searchInput = document.querySelector('input[type="search"]');
        if (searchInput) searchInput.focus();
    }

    showShortcutHelp() {
        // Show modal with all keyboard shortcuts
        const modal = document.createElement('div');
        modal.className = 'shortcut-help-modal';
        modal.innerHTML = `
            <div class="modal-content">
                <h3>⌨️ Keyboard Shortcuts</h3>
                <table class="shortcuts-table">
                    <tr>
                        <td><kbd>Ctrl</kbd> + <kbd>S</kbd></td>
                        <td>Save progress</td>
                    </tr>
                    <tr>
                        <td><kbd>Ctrl</kbd> + <kbd>Enter</kbd></td>
                        <td>Submit form</td>
                    </tr>
                    <tr>
                        <td><kbd>←</kbd> <kbd>→</kbd></td>
                        <td>Previous / Next step</td>
                    </tr>
                    <tr>
                        <td><kbd>/</kbd></td>
                        <td>Focus search</td>
                    </tr>
                    <tr>
                        <td><kbd>?</kbd></td>
                        <td>Show this help</td>
                    </tr>
                </table>
                <button onclick="this.closest('.shortcut-help-modal').remove()">
                    Close
                </button>
            </div>
        `;

        document.body.appendChild(modal);
    }

    showShortcutHint() {
        // Show subtle hint in footer
        const hint = document.createElement('div');
        hint.className = 'shortcut-hint';
        hint.innerHTML = 'Press <kbd>?</kbd> for keyboard shortcuts';
        document.body.appendChild(hint);
    }
}

// Initialize
new KeyboardShortcuts();
```

---

### Issue #15: PDF Preview Before Submission
**Priority**: MEDIUM-HIGH
**Time**: 2-3 hours
**Impact**: +35% user confidence, -50% post-filing questions

#### What It Does:
- Generate PDF preview of completed return
- Show what IRS will receive
- Allow review before final submission
- Mark as DRAFT with watermark

#### Files to Create:
- `src/export/pdf_previewer.py` (PDF generation for preview)

#### Files to Modify:
- `src/web/app.py` (add `/api/preview-pdf` route)
- `src/web/templates/index.html` (add preview button in Step 6)

#### Implementation:
```python
# src/export/pdf_previewer.py

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from io import BytesIO

class PDFPreviewer:
    """
    Generate PDF preview of tax return before filing.
    """

    def generate_preview(self, session_id: str) -> bytes:
        """
        Generate PDF preview with DRAFT watermark.
        """

        session = get_session(session_id)
        calc = session.final_calculation

        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Add DRAFT watermark
        self._add_watermark(c, width, height, "DRAFT - DO NOT FILE")

        # Page 1: Form 1040 Summary
        self._render_form_1040(c, session, calc)
        c.showPage()

        # Page 2: Supporting schedules if applicable
        if session.extracted_data.get("mortgage_interest", 0) > 0:
            self._render_schedule_a(c, session)
            c.showPage()

        if session.extracted_data.get("nonemployee_compensation", 0) > 0:
            self._render_schedule_c(c, session)
            c.showPage()

        c.save()

        pdf_bytes = buffer.getvalue()
        buffer.close()

        return pdf_bytes

    def _add_watermark(self, c, width, height, text):
        """Add diagonal DRAFT watermark."""
        c.saveState()
        c.setFont("Helvetica-Bold", 60)
        c.setFillColorRGB(0.9, 0.9, 0.9, alpha=0.3)
        c.translate(width/2, height/2)
        c.rotate(45)
        c.drawCentredString(0, 0, text)
        c.restoreState()

    def _render_form_1040(self, c, session, calc):
        """Render Form 1040 main page."""
        y = 750

        # Header
        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, y, "Form 1040 - U.S. Individual Income Tax Return")
        y -= 30

        c.setFont("Helvetica", 12)
        c.drawString(50, y, f"Tax Year: {session.tax_year}")
        y -= 20
        c.drawString(50, y, f"Name: {session.user_name}")
        y -= 20
        c.drawString(50, y, f"SSN: XXX-XX-{session.user_ssn[-4:]}")
        y -= 40

        # Income section
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y, "INCOME")
        y -= 25

        c.setFont("Helvetica", 11)
        self._draw_line_item(c, 50, y, "1", "Wages, salaries, tips",
                            f"${calc['wages']:,.0f}")
        y -= 20

        self._draw_line_item(c, 50, y, "2b", "Taxable interest",
                            f"${calc.get('interest', 0):,.0f}")
        y -= 20

        # ... more line items

        # Bottom line
        y -= 40
        c.setFont("Helvetica-Bold", 14)
        if calc['is_refund']:
            c.drawString(50, y, f"REFUND: ${calc['refund']:,.0f}")
        else:
            c.drawString(50, y, f"AMOUNT OWED: ${calc['owed']:,.0f}")

        # Legal notice
        y -= 60
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(0.8, 0, 0)
        notice = "This is a DRAFT preview only. Do not file this document with the IRS."
        c.drawString(50, y, notice)

    def _draw_line_item(self, c, x, y, line_num, description, amount):
        """Helper to draw a line item."""
        c.drawString(x, y, f"{line_num}.")
        c.drawString(x + 30, y, description)
        c.drawRightString(550, y, amount)
```

**UI Integration**:
```html
<!-- PDF Preview button in Step 6 (Review) -->
<div class="pdf-preview-section">
  <h3>📄 Preview Your Return</h3>
  <p>See exactly what your tax return looks like before filing.</p>

  <button class="btn-secondary" onclick="previewPDF()">
    👁️ Preview PDF
  </button>
</div>

<!-- PDF Preview Modal -->
<div class="pdf-preview-modal" id="pdfPreviewModal">
  <div class="modal-header">
    <h3>📄 Tax Return Preview</h3>
    <span class="draft-badge">DRAFT</span>
    <button class="close-btn" onclick="closePreview()">×</button>
  </div>

  <div class="pdf-viewer">
    <iframe id="pdfFrame" src=""></iframe>
  </div>

  <div class="modal-footer">
    <div class="preview-notice">
      <span class="icon">⚠️</span>
      <p>This is a preview only. Your actual filed return will be generated after professional review.</p>
    </div>

    <div class="modal-actions">
      <button class="btn-secondary" onclick="downloadDraft()">
        📥 Download Draft
      </button>
      <button class="btn-primary" onclick="proceedToReview()">
        Continue to CPA Review →
      </button>
    </div>
  </div>
</div>
```

**JavaScript**:
```javascript
async function previewPDF() {
    const loadingOverlay = showLoading('Generating preview...');

    try {
        const response = await fetch('/api/preview-pdf', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: currentSessionId })
        });

        if (!response.ok) throw new Error('Preview generation failed');

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);

        document.getElementById('pdfFrame').src = url;
        document.getElementById('pdfPreviewModal').classList.add('visible');

    } catch (error) {
        showError('Failed to generate preview. Please try again.');
    } finally {
        hideLoading(loadingOverlay);
    }
}
```

---

## SPRINT 3 SUMMARY

**Total Time**: 8-12 hours (1-2 days)
**Total Issues**: 5 (#11-15)
**Impact**: Quality-of-life improvements, professional polish

| Issue | Feature | Time | Priority | Impact |
|-------|---------|------|----------|--------|
| #11 | Prior Year Import | 2-3h | Medium | 60% faster filing |
| #12 | Smart Field Prefill | 1-2h | Medium | +15% completion |
| #13 | Contextual Help | 2h | Medium | -30% support requests |
| #14 | Keyboard Shortcuts | 1-2h | Low-Medium | +10% power user efficiency |
| #15 | PDF Preview | 2-3h | Medium-High | +35% user confidence |

**Ready to implement**: All designs complete
**Dependencies**: Google Places API key (Issue #12), reportlab library (Issue #15)

---

## SPRINT 4: POLISH & ADVANCED FEATURES ⏳
**Status**: ⬜ PENDING
**Estimated Time**: 10-15 hours (2-3 days)
**Priority**: MEDIUM-LOW
**Impact**: Professional polish, accessibility compliance, future-proofing

---

### Issue #16: Animated Transitions
**Priority**: LOW-MEDIUM
**Time**: 2-3 hours
**Impact**: +15% perceived quality, modern UX feel

#### What It Does:
- Smooth page transitions between steps
- Fade-in animations for content sections
- Slide-in for modals and tooltips
- Loading state animations
- Micro-interactions (button clicks, form submissions)

#### Files to Create:
- `src/web/static/css/animations.css` (animation library)
- `src/web/static/js/transition-manager.js` (transition coordination)

#### Implementation Steps:
```css
/* src/web/static/css/animations.css */

/* Page transitions */
@keyframes fadeIn {
    from {
        opacity: 0;
        transform: translateY(20px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes slideInRight {
    from {
        transform: translateX(100%);
        opacity: 0;
    }
    to {
        transform: translateX(0);
        opacity: 1;
    }
}

@keyframes scaleIn {
    from {
        transform: scale(0.95);
        opacity: 0;
    }
    to {
        transform: scale(1);
        opacity: 1;
    }
}

/* Apply to elements */
.step-content {
    animation: fadeIn 0.4s ease-out;
}

.modal {
    animation: scaleIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.tooltip {
    animation: fadeIn 0.2s ease-out;
}

/* Button interactions */
.btn-primary {
    transition: all 0.2s ease;
}

.btn-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

.btn-primary:active {
    transform: translateY(0);
}

/* Loading states */
@keyframes pulse {
    0%, 100% {
        opacity: 1;
    }
    50% {
        opacity: 0.5;
    }
}

.loading-skeleton {
    animation: pulse 1.5s ease-in-out infinite;
    background: linear-gradient(
        90deg,
        #f3f4f6 25%,
        #e5e7eb 50%,
        #f3f4f6 75%
    );
    background-size: 200% 100%;
}

@keyframes shimmer {
    0% {
        background-position: -200% 0;
    }
    100% {
        background-position: 200% 0;
    }
}

.loading-shimmer {
    animation: shimmer 2s infinite linear;
}

/* Form field focus */
input:focus,
textarea:focus,
select:focus {
    transition: all 0.3s ease;
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

/* Success/Error states */
@keyframes bounceIn {
    0% {
        transform: scale(0);
    }
    50% {
        transform: scale(1.1);
    }
    100% {
        transform: scale(1);
    }
}

.success-message {
    animation: bounceIn 0.5s ease-out;
}

.error-message {
    animation: bounceIn 0.5s ease-out;
}
```

```javascript
// src/web/static/js/transition-manager.js

class TransitionManager {
    /**
     * Coordinate smooth transitions throughout the app.
     */

    transitionToStep(currentStep, nextStep) {
        // Fade out current step
        const currentEl = document.getElementById(`step${currentStep}`);
        currentEl.style.animation = 'fadeOut 0.3s ease-out';

        setTimeout(() => {
            currentEl.style.display = 'none';

            // Fade in next step
            const nextEl = document.getElementById(`step${nextStep}`);
            nextEl.style.display = 'block';
            nextEl.style.animation = 'fadeIn 0.4s ease-out';

            // Scroll to top smoothly
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        }, 300);
    }

    showModal(modalElement) {
        modalElement.style.display = 'flex';

        // Add backdrop
        const backdrop = document.createElement('div');
        backdrop.className = 'modal-backdrop';
        backdrop.style.animation = 'fadeIn 0.3s ease-out';
        document.body.appendChild(backdrop);

        // Animate modal
        modalElement.style.animation = 'scaleIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)';
    }

    hideModal(modalElement) {
        modalElement.style.animation = 'fadeOut 0.2s ease-out';

        setTimeout(() => {
            modalElement.style.display = 'none';

            // Remove backdrop
            const backdrop = document.querySelector('.modal-backdrop');
            if (backdrop) backdrop.remove();
        }, 200);
    }

    showLoadingSkeleton(containerElement) {
        // Replace content with loading skeleton
        const skeleton = `
            <div class="loading-skeleton" style="height: 60px; margin-bottom: 12px;"></div>
            <div class="loading-skeleton" style="height: 40px; margin-bottom: 12px;"></div>
            <div class="loading-skeleton" style="height: 80px;"></div>
        `;
        containerElement.innerHTML = skeleton;
    }

    showSuccessAnimation(element, message) {
        element.innerHTML = `
            <div class="success-message">
                <span class="success-icon">✓</span>
                <span>${message}</span>
            </div>
        `;
    }
}

// Initialize
window.transitionManager = new TransitionManager();
```

**Accessibility Considerations**:
- Respect `prefers-reduced-motion` media query
- Provide instant transitions for users with motion sensitivity
- Ensure animations don't interfere with screen readers

```css
/* Respect user preferences */
@media (prefers-reduced-motion: reduce) {
    *,
    *::before,
    *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }
}
```

---

### Issue #17: Dark Mode
**Priority**: MEDIUM
**Time**: 3-4 hours
**Impact**: +20% user satisfaction (especially for evening filers)

#### What It Does:
- System preference detection (auto dark mode if OS is dark)
- Manual toggle switch
- Persistent preference storage
- Smooth color scheme transition
- Optimized color palette for readability

#### Files to Create:
- `src/web/static/css/dark-mode.css` (dark color scheme)
- `src/web/static/js/theme-manager.js` (theme switching logic)

#### Implementation:
```css
/* src/web/static/css/dark-mode.css */

:root {
    /* Light mode colors (default) */
    --bg-primary: #ffffff;
    --bg-secondary: #f9fafb;
    --text-primary: #111827;
    --text-secondary: #6b7280;
    --border-color: #e5e7eb;
    --accent-color: #3b82f6;
}

[data-theme="dark"] {
    /* Dark mode colors */
    --bg-primary: #1f2937;
    --bg-secondary: #111827;
    --text-primary: #f9fafb;
    --text-secondary: #9ca3af;
    --border-color: #374151;
    --accent-color: #60a5fa;
}

/* Apply to all elements */
body {
    background-color: var(--bg-primary);
    color: var(--text-primary);
    transition: background-color 0.3s ease, color 0.3s ease;
}

.card {
    background-color: var(--bg-secondary);
    border-color: var(--border-color);
}

input,
textarea,
select {
    background-color: var(--bg-primary);
    color: var(--text-primary);
    border-color: var(--border-color);
}

/* Dark mode specific adjustments */
[data-theme="dark"] input:focus {
    box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.2);
}

[data-theme="dark"] .btn-primary {
    background-color: #2563eb;
}

[data-theme="dark"] .btn-primary:hover {
    background-color: #1d4ed8;
}
```

```javascript
// src/web/static/js/theme-manager.js

class ThemeManager {
    constructor() {
        this.init();
    }

    init() {
        // Check for saved preference or system preference
        const savedTheme = localStorage.getItem('theme');
        const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

        if (savedTheme) {
            this.setTheme(savedTheme);
        } else if (systemPrefersDark) {
            this.setTheme('dark');
        } else {
            this.setTheme('light');
        }

        // Listen for system theme changes
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            if (!localStorage.getItem('theme')) {
                this.setTheme(e.matches ? 'dark' : 'light');
            }
        });
    }

    setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);

        // Update toggle switch if exists
        const toggle = document.getElementById('themeToggle');
        if (toggle) {
            toggle.checked = (theme === 'dark');
        }
    }

    toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        this.setTheme(newTheme);
    }
}

// Initialize
const themeManager = new ThemeManager();
```

**UI Toggle**:
```html
<!-- Theme toggle switch -->
<div class="theme-toggle-container">
    <label class="theme-toggle">
        <input type="checkbox" id="themeToggle" onchange="themeManager.toggleTheme()">
        <span class="toggle-slider"></span>
        <span class="toggle-icons">
            <span class="sun-icon">☀️</span>
            <span class="moon-icon">🌙</span>
        </span>
    </label>
</div>
```

---

### Issue #18: Voice Input
**Priority**: LOW
**Time**: 2-3 hours
**Impact**: Accessibility, hands-free convenience

#### What It Does:
- Voice-to-text for form fields
- Microphone button next to text inputs
- Real-time transcription preview
- Support for Chrome/Safari/Edge
- Fallback for unsupported browsers

#### Files to Create:
- `src/web/static/js/voice-input.js` (speech recognition)

#### Implementation:
```javascript
// src/web/static/js/voice-input.js

class VoiceInputManager {
    constructor() {
        this.recognition = null;
        this.initializeSpeechRecognition();
    }

    initializeSpeechRecognition() {
        // Check browser support
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            console.log('Speech recognition not supported');
            return;
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.recognition = new SpeechRecognition();

        this.recognition.continuous = false;
        this.recognition.interimResults = true;
        this.recognition.lang = 'en-US';

        this.recognition.onresult = (event) => {
            const transcript = Array.from(event.results)
                .map(result => result[0].transcript)
                .join('');

            this.handleTranscript(transcript, event.results[0].isFinal);
        };

        this.recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            this.showError('Voice input failed. Please try again.');
        };
    }

    enableVoiceInput(inputElement) {
        // Add microphone button
        const micButton = document.createElement('button');
        micButton.className = 'voice-input-btn';
        micButton.innerHTML = '🎤';
        micButton.type = 'button';
        micButton.setAttribute('aria-label', 'Start voice input');

        micButton.addEventListener('click', () => {
            this.startListening(inputElement, micButton);
        });

        // Insert button next to input
        inputElement.parentElement.appendChild(micButton);
    }

    startListening(targetInput, button) {
        if (!this.recognition) {
            alert('Voice input is not supported in your browser.');
            return;
        }

        this.currentInput = targetInput;
        button.classList.add('listening');
        button.innerHTML = '🔴'; // Recording indicator

        this.recognition.start();

        this.recognition.onend = () => {
            button.classList.remove('listening');
            button.innerHTML = '🎤';
        };
    }

    handleTranscript(transcript, isFinal) {
        if (this.currentInput) {
            // Show interim results in placeholder
            if (!isFinal) {
                this.currentInput.placeholder = transcript;
            } else {
                // Final result - insert into input
                this.currentInput.value = transcript;
                this.currentInput.placeholder = '';

                // Trigger input event for auto-save
                this.currentInput.dispatchEvent(new Event('input', { bubbles: true }));

                // Smart formatting for specific fields
                this.smartFormatField(this.currentInput, transcript);
            }
        }
    }

    smartFormatField(input, transcript) {
        const fieldType = input.getAttribute('data-type');

        if (fieldType === 'ssn') {
            // Parse spoken SSN: "one two three, forty-five, sixty-seven eighty-nine"
            const digits = this.parseSpokenNumbers(transcript);
            if (digits.length === 9) {
                input.value = `${digits.slice(0,3)}-${digits.slice(3,5)}-${digits.slice(5)}`;
            }
        } else if (fieldType === 'currency') {
            // Parse spoken currency: "eighty-five thousand dollars"
            const amount = this.parseCurrencyFromSpeech(transcript);
            input.value = amount;
        } else if (fieldType === 'date') {
            // Parse spoken date: "January fifteenth, nineteen ninety"
            const date = this.parseDateFromSpeech(transcript);
            input.value = date;
        }
    }

    parseSpokenNumbers(text) {
        // Convert spoken numbers to digits
        const numberMap = {
            'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
            'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9',
            'ten': '10', 'eleven': '11', 'twelve': '12', // etc.
        };

        let result = text.toLowerCase();
        for (const [word, digit] of Object.entries(numberMap)) {
            result = result.replace(new RegExp(word, 'g'), digit);
        }

        return result.replace(/\D/g, ''); // Remove non-digits
    }

    parseCurrencyFromSpeech(text) {
        // Basic implementation - would need more sophistication
        const match = text.match(/(\d+)\s*(thousand|hundred)?/i);
        if (match) {
            let amount = parseInt(match[1]);
            if (match[2] === 'thousand') amount *= 1000;
            if (match[2] === 'hundred') amount *= 100;
            return amount.toString();
        }
        return text;
    }

    parseDateFromSpeech(text) {
        // Simplified - would use a library like chrono-node in production
        const date = new Date(text);
        if (!isNaN(date)) {
            return date.toLocaleDateString('en-US');
        }
        return text;
    }
}

// Initialize and enable for all text inputs
document.addEventListener('DOMContentLoaded', () => {
    const voiceManager = new VoiceInputManager();

    document.querySelectorAll('input[type="text"], textarea').forEach(input => {
        voiceManager.enableVoiceInput(input);
    });
});
```

**CSS**:
```css
.voice-input-btn {
    margin-left: 8px;
    padding: 8px 12px;
    background: #f3f4f6;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
}

.voice-input-btn:hover {
    background: #e5e7eb;
}

.voice-input-btn.listening {
    background: #fee2e2;
    border-color: #ef4444;
    animation: pulse 1s infinite;
}

@keyframes pulse {
    0%, 100% {
        opacity: 1;
    }
    50% {
        opacity: 0.7;
    }
}
```

---

### Issue #19: Multi-Language Support (i18n)
**Priority**: LOW
**Time**: 3-4 hours (initial setup) + ongoing translation
**Impact**: Expands addressable market by 40%

#### What It Does:
- Support Spanish, Chinese, Vietnamese (top US immigrant languages)
- Language selector in header
- Persistent language preference
- Translation of all UI text
- RTL support for future Arabic

#### Files to Create:
- `src/web/static/js/i18n.js` (internationalization library)
- `src/locales/en.json` (English translations)
- `src/locales/es.json` (Spanish translations)
- `src/locales/zh.json` (Chinese translations)
- `src/locales/vi.json` (Vietnamese translations)

#### Implementation:
```json
// src/locales/en.json
{
    "nav": {
        "home": "Home",
        "file_taxes": "File Taxes",
        "help": "Help",
        "language": "Language"
    },
    "landing": {
        "title": "Smart Tax Filing Made Simple",
        "subtitle": "File your taxes in 3 minutes with AI-powered assistance",
        "express_lane": "⚡ Express Lane",
        "express_desc": "Snap your W-2, we'll handle the rest",
        "chat_mode": "💬 AI Chat",
        "chat_desc": "Tell us about your taxes conversationally",
        "guided_forms": "📝 Guided Forms",
        "guided_desc": "Step-by-step traditional filing"
    },
    "forms": {
        "ssn": "Social Security Number",
        "ssn_help": "Your 9-digit SSN from your Social Security card",
        "filing_status": "Filing Status",
        "dependents": "Number of Dependents",
        "submit": "Submit",
        "next": "Next",
        "back": "Back",
        "save": "Save Progress"
    },
    "validation": {
        "required": "This field is required",
        "invalid_ssn": "Please enter a valid SSN (XXX-XX-XXXX)",
        "invalid_email": "Please enter a valid email address"
    },
    "messages": {
        "saving": "Saving...",
        "saved": "All changes saved",
        "error": "An error occurred. Please try again.",
        "success": "Success!"
    }
}
```

```json
// src/locales/es.json
{
    "nav": {
        "home": "Inicio",
        "file_taxes": "Presentar Impuestos",
        "help": "Ayuda",
        "language": "Idioma"
    },
    "landing": {
        "title": "Declaración de Impuestos Inteligente y Simple",
        "subtitle": "Presente sus impuestos en 3 minutos con asistencia de IA",
        "express_lane": "⚡ Vía Rápida",
        "express_desc": "Tome una foto de su W-2, nosotros hacemos el resto",
        "chat_mode": "💬 Chat IA",
        "chat_desc": "Cuéntenos sobre sus impuestos de forma conversacional",
        "guided_forms": "📝 Formularios Guiados",
        "guided_desc": "Presentación tradicional paso a paso"
    },
    "forms": {
        "ssn": "Número de Seguro Social",
        "ssn_help": "Su SSN de 9 dígitos de su tarjeta de Seguro Social",
        "filing_status": "Estado de Presentación",
        "dependents": "Número de Dependientes",
        "submit": "Enviar",
        "next": "Siguiente",
        "back": "Atrás",
        "save": "Guardar Progreso"
    },
    "validation": {
        "required": "Este campo es obligatorio",
        "invalid_ssn": "Por favor ingrese un SSN válido (XXX-XX-XXXX)",
        "invalid_email": "Por favor ingrese un correo electrónico válido"
    },
    "messages": {
        "saving": "Guardando...",
        "saved": "Todos los cambios guardados",
        "error": "Ocurrió un error. Por favor intente de nuevo.",
        "success": "¡Éxito!"
    }
}
```

```javascript
// src/web/static/js/i18n.js

class I18nManager {
    constructor(defaultLang = 'en') {
        this.currentLang = defaultLang;
        this.translations = {};
        this.init();
    }

    async init() {
        // Load saved preference or detect from browser
        const savedLang = localStorage.getItem('language');
        const browserLang = navigator.language.split('-')[0];

        this.currentLang = savedLang || browserLang || 'en';

        // Load translations
        await this.loadTranslations(this.currentLang);

        // Apply translations to page
        this.translatePage();
    }

    async loadTranslations(lang) {
        try {
            const response = await fetch(`/static/locales/${lang}.json`);
            this.translations = await response.json();
        } catch (error) {
            console.error(`Failed to load translations for ${lang}`, error);
            // Fallback to English
            if (lang !== 'en') {
                await this.loadTranslations('en');
            }
        }
    }

    t(key) {
        // Translate a key like "nav.home"
        const keys = key.split('.');
        let result = this.translations;

        for (const k of keys) {
            result = result[k];
            if (!result) {
                console.warn(`Translation missing for key: ${key}`);
                return key;
            }
        }

        return result;
    }

    translatePage() {
        // Find all elements with data-i18n attribute
        document.querySelectorAll('[data-i18n]').forEach(element => {
            const key = element.getAttribute('data-i18n');
            const translation = this.t(key);

            if (element.tagName === 'INPUT' && element.placeholder) {
                element.placeholder = translation;
            } else {
                element.textContent = translation;
            }
        });

        // Update lang attribute
        document.documentElement.setAttribute('lang', this.currentLang);
    }

    async changeLanguage(lang) {
        this.currentLang = lang;
        localStorage.setItem('language', lang);

        await this.loadTranslations(lang);
        this.translatePage();
    }
}

// Initialize
const i18n = new I18nManager();
```

**HTML Usage**:
```html
<!-- Language selector -->
<select id="langSelector" onchange="i18n.changeLanguage(this.value)">
    <option value="en">English</option>
    <option value="es">Español</option>
    <option value="zh">中文</option>
    <option value="vi">Tiếng Việt</option>
</select>

<!-- Translatable elements -->
<h1 data-i18n="landing.title">Smart Tax Filing Made Simple</h1>
<p data-i18n="landing.subtitle">File your taxes in 3 minutes with AI-powered assistance</p>
<button data-i18n="forms.submit">Submit</button>
<input type="text" data-i18n="forms.ssn" placeholder="Social Security Number">
```

---

### Issue #20: Accessibility Enhancements (WCAG 2.1 AA)
**Priority**: MEDIUM-HIGH (Legal requirement)
**Time**: 3-4 hours
**Impact**: Legal compliance, +30% addressable market

#### What It Does:
- Full keyboard navigation
- Screen reader optimization (ARIA labels)
- Color contrast compliance (4.5:1 minimum)
- Focus indicators
- Skip navigation links
- Alternative text for all images
- Form field labels and error announcements

#### Implementation Checklist:

**1. Keyboard Navigation**:
```javascript
// Ensure all interactive elements are keyboard accessible
document.querySelectorAll('button, a, input, select, textarea').forEach(el => {
    if (!el.hasAttribute('tabindex') && el.disabled) {
        el.setAttribute('tabindex', '-1');
    }
});

// Add skip navigation link
const skipNav = document.createElement('a');
skipNav.href = '#main-content';
skipNav.className = 'skip-nav';
skipNav.textContent = 'Skip to main content';
skipNav.style.cssText = `
    position: absolute;
    left: -9999px;
    z-index: 999;
`;

skipNav.addEventListener('focus', () => {
    skipNav.style.left = '10px';
    skipNav.style.top = '10px';
});

skipNav.addEventListener('blur', () => {
    skipNav.style.left = '-9999px';
});

document.body.insertBefore(skipNav, document.body.firstChild);
```

**2. ARIA Labels**:
```html
<!-- Proper form labels -->
<label for="ssn" id="ssn-label">
    Social Security Number
    <span class="required" aria-label="required">*</span>
</label>
<input
    type="text"
    id="ssn"
    name="ssn"
    aria-labelledby="ssn-label"
    aria-describedby="ssn-help"
    aria-required="true"
    aria-invalid="false"
>
<p id="ssn-help" class="help-text">
    Your 9-digit SSN from your Social Security card
</p>

<!-- Dynamic content updates -->
<div
    role="status"
    aria-live="polite"
    aria-atomic="true"
    id="saveStatus"
>
    All changes saved
</div>

<!-- Modal dialogs -->
<div
    role="dialog"
    aria-modal="true"
    aria-labelledby="modal-title"
    aria-describedby="modal-description"
    class="modal"
>
    <h2 id="modal-title">Confirm Submission</h2>
    <p id="modal-description">Are you ready to submit your tax return?</p>
    <button aria-label="Confirm and submit">Confirm</button>
    <button aria-label="Cancel and go back">Cancel</button>
</div>

<!-- Progress indicators -->
<div role="progressbar" aria-valuenow="3" aria-valuemin="1" aria-valuemax="6" aria-label="Step 3 of 6">
    <span class="sr-only">Step 3 of 6: Income Information</span>
    <div class="progress-bar" style="width: 50%"></div>
</div>
```

**3. Color Contrast**:
```css
/* Ensure all text meets WCAG AA (4.5:1) or AAA (7:1) contrast */

/* PASS: #111827 on #ffffff = 16.7:1 */
.text-primary {
    color: #111827;
}

/* PASS: #1f2937 on #ffffff = 14.4:1 */
.text-secondary {
    color: #1f2937;
}

/* FAIL: #9ca3af on #ffffff = 2.9:1 - Too light! */
/* FIX: Use darker gray */
.text-muted {
    color: #6b7280; /* 4.5:1 contrast */
}

/* Button states */
.btn-primary {
    background: #2563eb; /* Blue */
    color: #ffffff; /* 8.6:1 contrast - PASS */
}

.btn-primary:focus {
    outline: 3px solid #2563eb;
    outline-offset: 2px;
}

/* Error states - ensure color is not the only indicator */
.error {
    color: #dc2626; /* Red */
    border-left: 4px solid #dc2626; /* Visual indicator */
}

.error::before {
    content: '⚠️ '; /* Icon indicator */
}

/* Focus indicators */
*:focus {
    outline: 3px solid #2563eb;
    outline-offset: 2px;
}

/* Don't remove focus indicators! */
*:focus:not(:focus-visible) {
    outline: none;
}

*:focus-visible {
    outline: 3px solid #2563eb;
    outline-offset: 2px;
}
```

**4. Error Announcements**:
```javascript
function announceError(fieldId, errorMessage) {
    // Update field aria-invalid
    const field = document.getElementById(fieldId);
    field.setAttribute('aria-invalid', 'true');
    field.setAttribute('aria-describedby', `${fieldId}-error`);

    // Create or update error message
    let errorEl = document.getElementById(`${fieldId}-error`);
    if (!errorEl) {
        errorEl = document.createElement('p');
        errorEl.id = `${fieldId}-error`;
        errorEl.className = 'error-message';
        errorEl.setAttribute('role', 'alert'); // Screen reader announces immediately
        field.parentElement.appendChild(errorEl);
    }

    errorEl.textContent = errorMessage;
}

function clearError(fieldId) {
    const field = document.getElementById(fieldId);
    field.setAttribute('aria-invalid', 'false');
    field.removeAttribute('aria-describedby');

    const errorEl = document.getElementById(`${fieldId}-error`);
    if (errorEl) errorEl.remove();
}
```

**5. Screen Reader Only Text**:
```css
/* Visually hidden but readable by screen readers */
.sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border-width: 0;
}

.sr-only-focusable:focus {
    position: static;
    width: auto;
    height: auto;
    overflow: visible;
    clip: auto;
    white-space: normal;
}
```

**Testing Tools**:
- axe DevTools (browser extension)
- WAVE (Web Accessibility Evaluation Tool)
- NVDA/JAWS (screen reader testing)
- Keyboard-only navigation testing

---

## SPRINT 4 SUMMARY

**Total Time**: 10-15 hours (2-3 days)
**Total Issues**: 5 (#16-20)
**Impact**: Professional polish, legal compliance, broader market reach

| Issue | Feature | Time | Priority | Impact |
|-------|---------|------|----------|--------|
| #16 | Animated Transitions | 2-3h | Low-Medium | +15% perceived quality |
| #17 | Dark Mode | 3-4h | Medium | +20% user satisfaction |
| #18 | Voice Input | 2-3h | Low | Accessibility, convenience |
| #19 | Multi-Language | 3-4h | Low | +40% addressable market |
| #20 | Accessibility (WCAG 2.1) | 3-4h | Medium-High | Legal compliance |

**Ready to implement**: All designs complete
**Dependencies**: Web Speech API (Issue #18), Translation files (Issue #19)
**Legal Note**: Issue #20 (Accessibility) may be legally required depending on jurisdiction

---

## ENHANCEMENT ROADMAP: HIGH-VALUE FEATURES ⏳
**Status**: ⬜ PENDING
**Total Time**: 30-45 days (6-9 weeks)
**Priority**: STRATEGIC
**Impact**: Transform from compliance tool into comprehensive advisory platform

These enhancements address the top 3 pain points identified through CPA and client feedback:
1. Pre-Return Decision Chaos (Scenario Intelligence)
2. Client Data Chaos (Document Management)
3. Communication Inefficiency (Automation)

---

## PAIN POINT #1: PRE-RETURN DECISION CHAOS
**Focus**: Scenario Intelligence & Tax Planning
**Business Value**: Enable $500-2000 advisory engagements (vs $50 compliance filing)

---

### Enhancement 1.1: Entity Structure Comparison Tool
**Priority**: HIGH
**Time**: 2-3 days
**Impact**: +40% business owner market, $1000-2000 per engagement
**Revenue Potential**: $200K+ annual (200 business planning sessions @ $1000 each)

#### What It Does:
- Compare S-Corp vs LLC vs Sole Proprietor tax implications
- Calculate self-employment tax savings
- Determine reasonable salary for S-Corp owners
- QBI (Qualified Business Income) deduction analysis
- State-specific tax considerations
- Break-even analysis for entity conversion

#### Business Case:
**Scenario**: Sole proprietor making $150K/year
- Current SE tax: $21,186 (15.3% on $138,500 cap + Medicare on rest)
- As S-Corp w/ $90K salary: $13,770 SE tax + payroll costs
- **Savings**: ~$5,000/year (minus $2K S-Corp compliance costs)
- **Client value**: $3K net savings first year, $5K/year ongoing

#### Files to Create:
- `src/recommendation/entity_optimizer.py` (core comparison engine)
- `src/web/entity_comparison_api.py` (REST API)
- `src/web/templates/entity_comparison.html` (UI)

#### Implementation:
```python
# src/recommendation/entity_optimizer.py

from dataclasses import dataclass
from typing import Dict, List, Tuple

@dataclass
class EntityAnalysis:
    entity_type: str
    total_tax: float
    federal_income_tax: float
    self_employment_tax: float
    state_tax: float
    qbi_deduction: float
    administrative_costs: float
    net_benefit: float
    complexity_score: int  # 1-10
    recommendations: List[str]
    cautions: List[str]

class EntityStructureOptimizer:
    """
    Compare tax implications of different business entity structures.

    Entities compared:
    - Sole Proprietorship (Schedule C)
    - Single-Member LLC (disregarded entity)
    - S-Corporation
    - C-Corporation (for high-earning businesses)
    """

    def __init__(self, tax_calculator):
        self.tax_calc = tax_calculator
        self.current_year = 2025

        # 2025 tax constants
        self.SE_TAX_RATE = 0.153  # 15.3%
        self.SE_WAGE_BASE = 168600  # Social Security wage base
        self.MEDICARE_RATE = 0.029  # 2.9%
        self.ADDITIONAL_MEDICARE_THRESHOLD = 200000  # Single
        self.QBI_THRESHOLD = 191950  # Single (2025)

    def compare_all_entities(
        self,
        business_income: float,
        business_expenses: float,
        filing_status: str,
        state: str,
        has_employees: bool = False
    ) -> Dict[str, EntityAnalysis]:
        """
        Run comprehensive comparison across all entity types.
        """

        net_profit = business_income - business_expenses

        comparisons = {
            "sole_proprietor": self.analyze_sole_proprietor(
                net_profit, filing_status, state
            ),
            "llc": self.analyze_llc(
                net_profit, filing_status, state
            ),
            "s_corp": self.analyze_s_corp(
                net_profit, filing_status, state, has_employees
            )
        }

        # Add C-Corp if income is very high
        if net_profit > 200000:
            comparisons["c_corp"] = self.analyze_c_corp(
                net_profit, filing_status, state
            )

        return comparisons

    def analyze_sole_proprietor(
        self,
        net_profit: float,
        filing_status: str,
        state: str
    ) -> EntityAnalysis:
        """
        Analyze tax implications as Sole Proprietor (Schedule C).
        """

        # Calculate self-employment tax
        se_tax = self.calculate_se_tax(net_profit)

        # QBI deduction (20% of qualified business income)
        qbi_deduction = self.calculate_qbi_deduction(
            net_profit, filing_status, entity_type="sole_prop"
        )

        # Federal income tax (after SE deduction and QBI deduction)
        se_deduction = se_tax * 0.5  # Deduct employer portion
        taxable_income = net_profit - se_deduction - qbi_deduction

        federal_income_tax = self.tax_calc.calculate_federal_tax(
            taxable_income, filing_status
        )

        # State tax
        state_tax = self.calculate_state_tax(
            taxable_income, state, filing_status
        )

        total_tax = se_tax + federal_income_tax + state_tax

        # Administrative costs (minimal for sole prop)
        admin_costs = 200  # Just accounting software

        return EntityAnalysis(
            entity_type="Sole Proprietorship",
            total_tax=total_tax,
            federal_income_tax=federal_income_tax,
            self_employment_tax=se_tax,
            state_tax=state_tax,
            qbi_deduction=qbi_deduction,
            administrative_costs=admin_costs,
            net_benefit=0,  # Baseline for comparison
            complexity_score=2,  # Very simple
            recommendations=[
                "✅ Simplest structure - minimal paperwork",
                "✅ Lowest setup and maintenance costs",
                "✅ Full QBI deduction available (if income < threshold)",
                "📝 File Schedule C with personal return"
            ],
            cautions=[
                "⚠️ Pay full self-employment tax (15.3%)",
                "⚠️ No separation between personal and business liability",
                "⚠️ Limited tax planning flexibility"
            ]
        )

    def analyze_llc(
        self,
        net_profit: float,
        filing_status: str,
        state: str
    ) -> EntityAnalysis:
        """
        Analyze Single-Member LLC (taxed as disregarded entity).

        Tax-wise, identical to sole prop, but with liability protection.
        """

        # Tax calculation identical to sole prop
        sole_prop_analysis = self.analyze_sole_proprietor(
            net_profit, filing_status, state
        )

        # Add LLC formation and annual fees
        llc_formation_cost = 500  # One-time (amortized over 5 years = $100/year)
        llc_annual_fee = 300  # Varies by state (CA is $800)
        admin_costs = 100 + 300  # Amortized formation + annual

        return EntityAnalysis(
            entity_type="Single-Member LLC",
            total_tax=sole_prop_analysis.total_tax,
            federal_income_tax=sole_prop_analysis.federal_income_tax,
            self_employment_tax=sole_prop_analysis.self_employment_tax,
            state_tax=sole_prop_analysis.state_tax + llc_annual_fee,
            qbi_deduction=sole_prop_analysis.qbi_deduction,
            administrative_costs=admin_costs,
            net_benefit=-admin_costs,  # Slightly more expensive than sole prop
            complexity_score=3,
            recommendations=[
                "✅ Personal liability protection",
                "✅ Professional appearance",
                "✅ Same tax treatment as sole prop",
                "✅ Can elect S-Corp or C-Corp taxation later"
            ],
            cautions=[
                "⚠️ Still pay full self-employment tax",
                f"⚠️ Annual state fees (${llc_annual_fee})",
                "⚠️ Need separate business bank account"
            ]
        )

    def analyze_s_corp(
        self,
        net_profit: float,
        filing_status: str,
        state: str,
        has_employees: bool
    ) -> EntityAnalysis:
        """
        Analyze S-Corporation taxation.

        Key: Owner takes "reasonable salary" (subject to SE tax),
        remainder as distributions (NOT subject to SE tax).
        """

        # Determine reasonable salary (IRS requirement)
        reasonable_salary = self.calculate_reasonable_salary(net_profit)

        # Distributions (not subject to SE tax)
        distributions = net_profit - reasonable_salary

        # Payroll taxes on salary only
        payroll_tax_employer = reasonable_salary * 0.0765  # Employer FICA
        payroll_tax_employee = reasonable_salary * 0.0765  # Employee FICA
        total_payroll_tax = payroll_tax_employer + payroll_tax_employee

        # QBI deduction (20% of qualified business income)
        # For S-Corp, QBI = distributions + salary
        qbi_deduction = self.calculate_qbi_deduction(
            net_profit, filing_status, entity_type="s_corp"
        )

        # Federal income tax on salary + distributions
        taxable_income = reasonable_salary + distributions - qbi_deduction
        federal_income_tax = self.tax_calc.calculate_federal_tax(
            taxable_income, filing_status
        )

        # State tax
        state_tax = self.calculate_state_tax(
            taxable_income, state, filing_status
        )

        total_tax = total_payroll_tax + federal_income_tax + state_tax

        # Administrative costs (higher for S-Corp)
        admin_costs = 2000  # Payroll processing + bookkeeping + tax prep
        if not has_employees:
            admin_costs += 500  # Need to set up payroll for yourself

        # Calculate savings vs sole prop
        sole_prop_total = self.analyze_sole_proprietor(
            net_profit, filing_status, state
        ).total_tax

        net_benefit = sole_prop_total - (total_tax + admin_costs)

        return EntityAnalysis(
            entity_type="S-Corporation",
            total_tax=total_tax,
            federal_income_tax=federal_income_tax,
            self_employment_tax=total_payroll_tax,
            state_tax=state_tax,
            qbi_deduction=qbi_deduction,
            administrative_costs=admin_costs,
            net_benefit=net_benefit,
            complexity_score=7,
            recommendations=[
                f"💰 Pay yourself ${reasonable_salary:,.0f} salary",
                f"💰 Take ${distributions:,.0f} as distributions (no SE tax)",
                f"💰 Estimated savings: ${net_benefit:,.0f}/year",
                "✅ Liability protection",
                "✅ QBI deduction available",
                "📝 File Form 1120-S (separate return)"
            ],
            cautions=[
                "⚠️ Must pay 'reasonable salary' (IRS scrutiny)",
                f"⚠️ Higher admin costs (~${admin_costs:,.0f}/year)",
                "⚠️ Payroll tax filings required (quarterly)",
                "⚠️ More complex bookkeeping",
                f"⚠️ Only worth it if saving > ${admin_costs:,.0f}"
            ]
        )

    def calculate_reasonable_salary(self, net_profit: float) -> float:
        """
        Determine reasonable salary for S-Corp owner.

        IRS guidelines (not explicit, but based on audits):
        - 40-60% of net profit is typical
        - Must be comparable to similar positions in industry
        - Cannot be zero or artificially low
        """

        # Conservative approach: 60% of net profit
        # (IRS is less likely to challenge)
        if net_profit < 40000:
            # Below $40K, S-Corp probably not worth it
            return net_profit * 0.8
        elif net_profit < 100000:
            return net_profit * 0.6
        elif net_profit < 200000:
            return net_profit * 0.5
        else:
            # High earners can take smaller percentage
            return net_profit * 0.4

    def calculate_se_tax(self, net_profit: float) -> float:
        """
        Calculate self-employment tax (Schedule SE).

        2025 rates:
        - Social Security: 12.4% on first $168,600
        - Medicare: 2.9% on all earnings
        - Additional Medicare: 0.9% on earnings > $200K (single)
        """

        # Apply 92.35% multiplier (deduct "employer" portion)
        net_se_income = net_profit * 0.9235

        # Social Security portion (capped)
        ss_taxable = min(net_se_income, self.SE_WAGE_BASE)
        ss_tax = ss_taxable * 0.124

        # Medicare portion (no cap)
        medicare_tax = net_se_income * 0.029

        # Additional Medicare tax for high earners
        additional_medicare = 0
        if net_se_income > self.ADDITIONAL_MEDICARE_THRESHOLD:
            additional_medicare = (net_se_income - self.ADDITIONAL_MEDICARE_THRESHOLD) * 0.009

        return ss_tax + medicare_tax + additional_medicare

    def calculate_qbi_deduction(
        self,
        net_profit: float,
        filing_status: str,
        entity_type: str
    ) -> float:
        """
        Calculate Qualified Business Income (QBI) deduction.

        Section 199A: Up to 20% deduction on qualified business income.

        Rules:
        - Phase-in thresholds (2025):
          - Single: $191,950 - $241,950
          - MFJ: $383,900 - $483,900
        - Above threshold: Limited for "specified service trades"
        - Below threshold: Full 20% deduction
        """

        # Simplified: Assume below threshold for now
        # (Would need more input to determine SSTB status)

        if filing_status == "single":
            threshold = self.QBI_THRESHOLD
        else:
            threshold = self.QBI_THRESHOLD * 2

        if net_profit <= threshold:
            # Full 20% deduction
            return net_profit * 0.20
        else:
            # Phase-out calculation (simplified)
            # In reality, this is more complex with W-2 wage / property limitations
            phase_out_range = 50000  # $50K phase-out range
            excess = net_profit - threshold

            if excess >= phase_out_range:
                return 0  # Fully phased out (if SSTB)
            else:
                reduction_pct = excess / phase_out_range
                return net_profit * 0.20 * (1 - reduction_pct)

    def generate_comparison_report(
        self,
        comparisons: Dict[str, EntityAnalysis]
    ) -> Dict:
        """
        Generate side-by-side comparison report.
        """

        # Sort by net benefit (highest savings first)
        sorted_entities = sorted(
            comparisons.items(),
            key=lambda x: x[1].net_benefit,
            reverse=True
        )

        best_entity = sorted_entities[0][1]

        return {
            "recommendation": best_entity.entity_type,
            "savings_vs_baseline": best_entity.net_benefit,
            "comparisons": {
                name: {
                    "total_tax": analysis.total_tax,
                    "se_tax": analysis.self_employment_tax,
                    "income_tax": analysis.federal_income_tax,
                    "state_tax": analysis.state_tax,
                    "admin_costs": analysis.administrative_costs,
                    "net_benefit": analysis.net_benefit,
                    "complexity": analysis.complexity_score,
                    "pros": analysis.recommendations,
                    "cons": analysis.cautions
                }
                for name, analysis in comparisons.items()
            },
            "decision_matrix": self.create_decision_matrix(comparisons)
        }

    def create_decision_matrix(
        self,
        comparisons: Dict[str, EntityAnalysis]
    ) -> List[str]:
        """
        Provide decision guidance based on business specifics.
        """

        guidelines = []

        # Analyze the comparison results
        sole_prop = comparisons.get("sole_proprietor")
        s_corp = comparisons.get("s_corp")

        if s_corp and s_corp.net_benefit > 3000:
            guidelines.append(
                f"🎯 **S-Corp Recommended**: Save ${s_corp.net_benefit:,.0f}/year"
            )
            guidelines.append(
                "✅ Savings exceed administrative costs significantly"
            )
        elif s_corp and s_corp.net_benefit > 0:
            guidelines.append(
                f"⚖️ **S-Corp Marginal**: Save ${s_corp.net_benefit:,.0f}/year"
            )
            guidelines.append(
                "⚠️ Savings are modest - consider complexity vs benefit"
            )
        else:
            guidelines.append(
                "📝 **Stay Sole Prop/LLC**: S-Corp not beneficial at current income"
            )
            guidelines.append(
                "✅ Simplicity is worth more than minimal tax savings"
            )

        # Add income-based guidance
        if sole_prop:
            profit = sole_prop.total_tax / 0.30  # Rough estimate

            if profit < 40000:
                guidelines.append(
                    "💡 Under $40K profit: Stay sole prop/LLC"
                )
            elif profit < 100000:
                guidelines.append(
                    "💡 $40K-$100K profit: S-Corp starts making sense"
                )
            else:
                guidelines.append(
                    "💡 Over $100K profit: S-Corp likely worthwhile"
                )

        return guidelines
```

#### UI Integration:
```html
<!-- Entity Comparison Tool -->
<div class="entity-comparison-container">
    <h2>🏢 Business Entity Comparison</h2>
    <p>Find the best tax structure for your business</p>

    <!-- Input form -->
    <form id="entityComparisonForm">
        <div class="form-group">
            <label>Business Income (Revenue)</label>
            <input type="number" id="businessIncome" placeholder="$150,000">
        </div>

        <div class="form-group">
            <label>Business Expenses</label>
            <input type="number" id="businessExpenses" placeholder="$30,000">
        </div>

        <div class="form-group">
            <label>Filing Status</label>
            <select id="filingStatus">
                <option value="single">Single</option>
                <option value="married_jointly">Married Filing Jointly</option>
            </select>
        </div>

        <div class="form-group">
            <label>State</label>
            <select id="state">
                <option value="CA">California</option>
                <option value="TX">Texas</option>
                <!-- ... all states ... -->
            </select>
        </div>

        <button type="submit" class="btn-primary">
            Compare Entities
        </button>
    </form>

    <!-- Comparison results -->
    <div id="comparisonResults" class="comparison-grid">
        <!-- Sole Prop Card -->
        <div class="entity-card">
            <h3>📝 Sole Proprietorship</h3>
            <div class="total-tax">
                <span class="label">Total Tax:</span>
                <span class="amount">$28,453</span>
            </div>
            <div class="breakdown">
                <div class="breakdown-item">
                    <span>Self-Employment Tax:</span>
                    <span>$18,228</span>
                </div>
                <div class="breakdown-item">
                    <span>Income Tax:</span>
                    <span>$8,225</span>
                </div>
                <div class="breakdown-item">
                    <span>State Tax:</span>
                    <span>$2,000</span>
                </div>
            </div>
            <div class="admin-costs">
                <span>Admin Costs:</span>
                <span>$200/year</span>
            </div>
            <div class="complexity">
                Complexity: ⭐⭐ (Simple)
            </div>
        </div>

        <!-- S-Corp Card -->
        <div class="entity-card recommended">
            <div class="recommended-badge">💰 BEST VALUE</div>
            <h3>🏢 S-Corporation</h3>
            <div class="total-tax">
                <span class="label">Total Tax:</span>
                <span class="amount savings">$23,175</span>
            </div>
            <div class="savings-highlight">
                Save $5,278/year vs Sole Prop!
            </div>
            <div class="breakdown">
                <div class="breakdown-item">
                    <span>Payroll Tax (on $72K salary):</span>
                    <span>$11,016</span>
                </div>
                <div class="breakdown-item">
                    <span>Income Tax:</span>
                    <span>$10,159</span>
                </div>
                <div class="breakdown-item">
                    <span>State Tax:</span>
                    <span>$2,000</span>
                </div>
            </div>
            <div class="admin-costs">
                <span>Admin Costs:</span>
                <span>$2,000/year</span>
            </div>
            <div class="net-benefit">
                <strong>Net Benefit: $3,278/year</strong>
            </div>
            <div class="complexity">
                Complexity: ⭐⭐⭐⭐⭐⭐⭐ (Complex)
            </div>
        </div>
    </div>

    <!-- Decision guidance -->
    <div class="decision-guidance">
        <h3>🎯 Our Recommendation</h3>
        <div class="recommendation-box">
            <p><strong>Convert to S-Corporation</strong></p>
            <ul>
                <li>✅ Save $3,278/year after all costs</li>
                <li>✅ Savings justify the additional complexity</li>
                <li>✅ At your income level ($120K profit), S-Corp is optimal</li>
            </ul>

            <h4>Next Steps:</h4>
            <ol>
                <li>Consult with a CPA to confirm (we can connect you)</li>
                <li>File Articles of Incorporation with your state</li>
                <li>File Form 2553 (S-Corp election) with IRS</li>
                <li>Set up payroll system</li>
                <li>Establish business bank account</li>
            </ol>

            <button class="btn-primary">
                Schedule S-Corp Consultation ($299)
            </button>
        </div>
    </div>
</div>
```

**JavaScript API Call**:
```javascript
async function compareEntities() {
    const data = {
        business_income: parseFloat(document.getElementById('businessIncome').value),
        business_expenses: parseFloat(document.getElementById('businessExpenses').value),
        filing_status: document.getElementById('filingStatus').value,
        state: document.getElementById('state').value,
        has_employees: false
    };

    const response = await fetch('/api/entity-comparison', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });

    const comparison = await response.json();
    displayComparison(comparison);
}
```

**Testing Scenarios**:
- [ ] Low profit ($30K): Confirm sole prop recommended
- [ ] Medium profit ($80K): Confirm S-Corp marginally beneficial
- [ ] High profit ($200K): Confirm S-Corp highly beneficial
- [ ] State variations (CA vs TX)
- [ ] Different filing statuses

---

### Enhancement 1.2: Multi-Year Tax Projection Engine
**Priority**: MEDIUM-HIGH
**Time**: 4-5 days
**Impact**: Enable year-round advisory revenue, client retention
**Revenue Potential**: $300K+ annual (300 planning sessions @ $1000 each)

#### What It Does:
- Project tax liability over 3-5 years
- Model income growth, inflation, tax law changes
- Roth conversion ladder planning
- Retirement contribution optimization over time
- Capital gains harvesting strategies
- Year-by-year tax bracket analysis

#### Business Case:
Turn one-time tax clients into year-round planning clients:
- Current model: $50-200 per tax return (once per year)
- Planning model: $1000-2000 per year (ongoing relationship)
- **5-10x revenue per client**

#### Files to Create:
- `src/projection/multi_year_projector.py`
- `src/projection/growth_assumptions.py`
- `src/web/projection_api.py`
- `src/web/templates/multi_year_projection.html`

#### Implementation:
```python
# src/projection/multi_year_projector.py

from dataclasses import dataclass
from typing import List, Dict
import numpy as np

@dataclass
class YearProjection:
    year: int
    gross_income: float
    adjusted_gross_income: float
    taxable_income: float
    federal_tax: float
    state_tax: float
    total_tax: float
    effective_rate: float
    marginal_bracket: str
    retirement_contributions: float
    roth_conversions: float
    capital_gains: float
    recommendations: List[str]

class MultiYearTaxProjector:
    """
    Project tax implications over multiple years.

    Considers:
    - Income growth
    - Inflation adjustments to brackets/deductions
    - Retirement savings strategies
    - Roth conversion opportunities
    - Tax law sunsets (2025 TCJA provisions)
    """

    def __init__(self, tax_calculator):
        self.tax_calc = tax_calculator
        self.current_year = 2025

    def project_years(
        self,
        current_session: Dict,
        years_ahead: int = 3,
        assumptions: Dict = None
    ) -> List[YearProjection]:
        """
        Project tax situation for next N years.
        """

        # Default assumptions
        if not assumptions:
            assumptions = {
                "wage_growth_rate": 0.03,  # 3% annual wage growth
                "investment_growth_rate": 0.07,  # 7% stock market return
                "inflation_rate": 0.025,  # 2.5% inflation
                "401k_contribution_increase": 0.05,  # Increase by 5% per year
                "roth_conversion_strategy": "bracket_fill"  # Fill 24% bracket
            }

        projections = []

        # Start with current year data
        current_income = current_session.get("wages", 0)
        current_401k = current_session.get("retirement_401k", 0)
        current_investments = current_session.get("investment_balance", 100000)

        for year_offset in range(years_ahead + 1):
            year = self.current_year + year_offset

            # Project income growth
            projected_income = current_income * (
                (1 + assumptions["wage_growth_rate"]) ** year_offset
            )

            # Project retirement contributions
            projected_401k = current_401k * (
                (1 + assumptions["401k_contribution_increase"]) ** year_offset
            )

            # Cap at annual limit (with inflation adjustment)
            contribution_limit = 23000 * (
                (1 + assumptions["inflation_rate"]) ** year_offset
            )
            projected_401k = min(projected_401k, contribution_limit)

            # Project investment growth
            projected_investments = current_investments * (
                (1 + assumptions["investment_growth_rate"]) ** year_offset
            )

            # Calculate AGI
            agi = projected_income - projected_401k

            # Roth conversion opportunity
            roth_conversion = self.calculate_optimal_roth_conversion(
                agi,
                current_session.get("filing_status", "single"),
                assumptions["roth_conversion_strategy"]
            )

            # Adjust AGI for Roth conversion (adds to income)
            agi += roth_conversion

            # Calculate tax
            standard_deduction = self.get_standard_deduction_with_inflation(
                current_session.get("filing_status", "single"),
                year_offset,
                assumptions["inflation_rate"]
            )

            taxable_income = max(0, agi - standard_deduction)

            federal_tax = self.tax_calc.calculate_federal_tax_with_inflation(
                taxable_income,
                current_session.get("filing_status", "single"),
                year_offset,
                assumptions["inflation_rate"]
            )

            state_tax = self.calculate_state_tax_projection(
                taxable_income,
                current_session.get("state", "CA"),
                year_offset,
                assumptions["inflation_rate"]
            )

            total_tax = federal_tax + state_tax
            effective_rate = total_tax / agi if agi > 0 else 0

            # Determine marginal bracket
            marginal_bracket = self.tax_calc.get_marginal_bracket(
                taxable_income,
                current_session.get("filing_status", "single")
            )

            # Generate year-specific recommendations
            recommendations = self.generate_year_recommendations(
                year,
                agi,
                projected_401k,
                contribution_limit,
                roth_conversion,
                marginal_bracket
            )

            projection = YearProjection(
                year=year,
                gross_income=projected_income,
                adjusted_gross_income=agi,
                taxable_income=taxable_income,
                federal_tax=federal_tax,
                state_tax=state_tax,
                total_tax=total_tax,
                effective_rate=effective_rate,
                marginal_bracket=marginal_bracket,
                retirement_contributions=projected_401k,
                roth_conversions=roth_conversion,
                capital_gains=0,  # Could add capital gains harvesting logic
                recommendations=recommendations
            )

            projections.append(projection)

        return projections

    def calculate_optimal_roth_conversion(
        self,
        agi: float,
        filing_status: str,
        strategy: str
    ) -> float:
        """
        Calculate optimal Roth conversion amount.

        Strategies:
        - "none": No Roth conversions
        - "bracket_fill": Convert enough to fill current bracket
        - "fixed_amount": Convert fixed amount each year
        - "percentage": Convert percentage of traditional IRA
        """

        if strategy == "none":
            return 0

        elif strategy == "bracket_fill":
            # Convert enough to fill 24% bracket (not go into 32%)
            # 2025 brackets (single): 24% ends at $191,950

            if filing_status == "single":
                bracket_top = 191950
            else:
                bracket_top = 383900  # MFJ

            # How much room in bracket?
            room_in_bracket = max(0, bracket_top - agi)

            # Convert up to half the room (conservative)
            return room_in_bracket * 0.5

        elif strategy == "fixed_amount":
            return 10000  # Convert $10K per year

        else:
            return 0

    def generate_year_recommendations(
        self,
        year: int,
        agi: float,
        retirement_contribution: float,
        contribution_limit: float,
        roth_conversion: float,
        marginal_bracket: str
    ) -> List[str]:
        """
        Generate year-specific tax recommendations.
        """

        recommendations = []

        # Retirement contribution recommendation
        if retirement_contribution < contribution_limit:
            shortfall = contribution_limit - retirement_contribution
            potential_savings = shortfall * float(marginal_bracket.strip('%')) / 100

            recommendations.append(
                f"💰 **{year}**: Max out 401(k) - contribute ${shortfall:,.0f} more "
                f"(save ${potential_savings:,.0f} in taxes)"
            )

        # Roth conversion recommendation
        if roth_conversion > 0:
            recommendations.append(
                f"🔄 **{year}**: Convert ${roth_conversion:,.0f} to Roth IRA "
                f"while in {marginal_bracket} bracket"
            )

        # TCJA sunset warning (if applicable)
        if year >= 2026:
            recommendations.append(
                f"⚠️ **{year}**: TCJA tax cuts expired - brackets increased, "
                f"standard deduction decreased"
            )

        return recommendations

    def compare_strategies(
        self,
        current_session: Dict,
        strategies: List[Dict]
    ) -> Dict:
        """
        Compare multiple strategies side-by-side.

        Example strategies:
        1. Current path (no changes)
        2. Max 401(k) contributions
        3. Roth conversion ladder
        4. HSA + backdoor Roth
        """

        comparisons = {}

        for strategy in strategies:
            projections = self.project_years(
                current_session,
                years_ahead=3,
                assumptions=strategy["assumptions"]
            )

            # Calculate cumulative metrics
            total_tax_4_years = sum(p.total_tax for p in projections)
            total_retirement_savings = sum(p.retirement_contributions for p in projections)
            total_roth_conversions = sum(p.roth_conversions for p in projections)

            comparisons[strategy["name"]] = {
                "projections": projections,
                "total_tax": total_tax_4_years,
                "retirement_savings": total_retirement_savings,
                "roth_conversions": total_roth_conversions,
                "net_worth_increase": self.estimate_net_worth_increase(projections)
            }

        return comparisons
```

---

### Remaining Enhancements (Summary)

**Note**: The above two enhancements (1.1 and 1.2) show the level of implementation detail. The remaining enhancements follow similar patterns. Full implementation details for all enhancements can be found in `/docs/MASTER_IMPLEMENTATION_ROADMAP.md` and `/docs/VALUE_ADDITION_OPPORTUNITIES.md`.

#### Enhancement 1.3: Interactive Scenario API
- **Time**: 2-3 days
- **Priority**: HIGH
- **Files**: `src/web/scenario_api.py`, `src/web/templates/scenario_comparison.html`
- **Key Feature**: Real-time what-if analysis with instant recalculation

#### Enhancement 2.1: Smart Document Organization
- **Time**: 3-4 days
- **Priority**: MEDIUM
- **Files**: `src/document/smart_organizer.py`, `src/document/duplicate_detector.py`
- **Key Feature**: Auto-categorize documents, detect duplicates, version control

#### Enhancement 2.2: OCR Quality Enhancement
- **Time**: 2-3 days
- **Priority**: HIGH
- **Files**: `src/services/ocr/ocr_engine.py` (modifications)
- **Key Feature**: Multi-engine fallback, confidence scoring, learning from corrections

#### Enhancement 3.1: Smart Request System
- **Time**: 3-4 days
- **Priority**: MEDIUM
- **Files**: `src/communication/smart_request_system.py`
- **Key Feature**: Template-based requests, automatic follow-ups, client portal

#### Enhancement 3.2: Progress Notifications
- **Time**: 2-3 days
- **Priority**: LOW
- **Files**: `src/communication/notification_engine.py`
- **Key Feature**: Automatic status updates, webhooks, email/SMS integration

---

## ADVISORY REPORT IMPLEMENTATION ⏳
**Status**: ⬜ PENDING
**Total Time**: 17-24 days (3.5-5 weeks)
**Priority**: VERY HIGH
**Impact**: Transform $50 compliance into $500-2000 advisory service

Complete design documents already created:
1. `/docs/ADVISORY_COMPUTATION_REPORT_DESIGN.md` (Sections 1-2)
2. `/docs/ADVISORY_COMPUTATION_REPORT_SCENARIOS.md` (Sections 3-5)
3. `/docs/ADVISORY_COMPUTATION_REPORT_IMPLEMENTATION.md` (Sections 6-7 + Technical)
4. `/docs/ADVISORY_REPORT_QUICK_START.md` (Implementation roadmap)

### 8 Implementation Phases:

**Phase 1: Core Report Engine** (3-4 days)
- Create `AdvisoryComputationReportGenerator` class
- Implement executive summary generation
- Implement Form 1040 line-by-line computation
- Connect to existing tax calculator

**Phase 2: Scenario Comparison Engine** (2-3 days)
- Create `ScenarioEngine` class
- Define scenario templates (Max 401k, HSA, Itemize, etc.)
- Build comparison matrix
- Implement break-even analysis

**Phase 3: Multi-Year Projection** (2 days)
- Create `MultiYearProjector` class (partially covered in Enhancement 1.2)
- Project 3-year tax liability
- Calculate cumulative benefits
- Generate strategic timeline

**Phase 4: Strategic Recommendations** (2-3 days)
- Enhance `RecommendationEngine`
- Generate implementation steps
- Calculate budget impact
- Identify cautions and pro tips

**Phase 5: PDF Export System** (3-4 days)
- Create `AdvisoryPDFExporter` class using ReportLab
- Design professional templates
- Implement charts and visualizations
- Add DRAFT watermarking system

**Phase 6: API Integration** (1-2 days)
- Create REST endpoints
- Implement background processing
- Add caching layer
- Build polling system for async generation

**Phase 7: Frontend Integration** (2-3 days)
- Create report preview UI
- Build scenario comparison table
- Add expand/collapse recommendations
- Implement PDF download

**Phase 8: Testing & Validation** (2-3 days)
- Unit tests for all sections
- End-to-end integration tests
- CPA professional review
- Multi-scenario validation

---

## COMPLETE TASK INVENTORY SUMMARY

### ✅ COMPLETED
- **Sprint 1**: 5 issues (100%)
- **Sprint 2**: 5 issues (100%)
- **Backend Audit**: All APIs verified
- **Advisory Report Design**: 4 comprehensive documents (122 pages)
- **Unwritten Wisdom**: 70+ page knowledge base
- **Value Addition Analysis**: 6 features designed
- **Master Roadmap**: 16-week implementation plan

### ⏳ PENDING - READY TO IMPLEMENT

#### Immediate Priority (Week 1-2)
- [ ] **Sprint 3** (5 issues, 8-12 hours)
  - Issue #11: Prior Year Import (2-3h)
  - Issue #12: Smart Field Prefill (1-2h)
  - Issue #13: Contextual Help (2h)
  - Issue #14: Keyboard Shortcuts (1-2h)
  - Issue #15: PDF Preview (2-3h)

#### High Priority (Week 3-7)
- [ ] **Advisory Report System** (8 phases, 17-24 days)
  - Complete professional-grade 14-21 page reports
  - Enable $500-2000 advisory revenue per engagement
  - **40x revenue increase potential**

- [ ] **Entity Structure Comparison** (2-3 days)
  - S-Corp vs LLC vs Sole Prop analysis
  - $200K+ annual revenue potential

- [ ] **Multi-Year Projection** (4-5 days)
  - 3-5 year tax planning
  - $300K+ annual revenue potential

#### Medium Priority (Week 8-13)
- [ ] **Sprint 4** (5 issues, 10-15 hours)
  - Issue #16: Animated Transitions (2-3h)
  - Issue #17: Dark Mode (3-4h)
  - Issue #18: Voice Input (2-3h)
  - Issue #19: Multi-Language (3-4h)
  - Issue #20: Accessibility WCAG 2.1 (3-4h)

- [ ] **Remaining Enhancement Roadmap** (10-15 days)
  - Scenario API, Document Organization, OCR Enhancement
  - Communication Automation, Notifications

#### Long-Term (Week 14-24)
- [ ] **Advanced Features & Polish** (15-20 days)
  - Advanced analytics dashboard
  - Mobile app development
  - API integrations (QuickBooks, Xero, etc.)

---

## ESTIMATED TOTAL WORK REMAINING

### Time Breakdown
| Category | Items | Days | Hours |
|----------|-------|------|-------|
| Sprint 3 | 5 issues | 0.5-1 | 8-12 |
| Sprint 4 | 5 issues | 1-2 | 10-15 |
| Advisory Report | 8 phases | 17-24 | 136-192 |
| Entity Comparison | 1 feature | 2-3 | 16-24 |
| Multi-Year Projection | 1 feature | 4-5 | 32-40 |
| Other Enhancements | 5 features | 10-15 | 80-120 |
| **TOTAL** | **25 features** | **35-50 days** | **282-403 hours** |

### Resource Requirements
- **Senior Backend Developer**: 25-35 days
- **Frontend Developer**: 10-15 days
- **Designer**: 5-7 days (PDF templates, charts)
- **CPA Advisor**: 3-5 days (validation, review)
- **QA Tester**: 5-7 days (comprehensive testing)

### Budget Estimate (Industry Rates)
- Senior Backend: 35 days × $800/day = **$28,000**
- Frontend Dev: 15 days × $700/day = **$10,500**
- Designer: 7 days × $600/day = **$4,200**
- CPA Advisor: 5 days × $500/day = **$2,500**
- QA Tester: 7 days × $500/day = **$3,500**
- **Total**: **$48,700** (for complete platform transformation)

---

## RECOMMENDED IMPLEMENTATION SEQUENCE

### Phase 1: Quick Wins (Week 1-2)
**Goal**: Improve UX, reduce friction
1. Sprint 3 Implementation (all 5 issues)
2. Deploy and gather user feedback
**Estimated**: 8-12 hours

### Phase 2: Advisory Foundation (Week 3-9)
**Goal**: Build revenue-generating advisory capability
1. Advisory Report Core (Phases 1-4)
2. Begin PDF Export System
3. Entity Structure Comparison Tool
**Estimated**: 3-4 weeks

### Phase 3: Advisory Completion (Week 10-12)
**Goal**: Launch complete advisory service
1. Complete PDF Export & API Integration
2. Frontend Integration
3. Multi-Year Projection Engine
4. Comprehensive Testing
**Estimated**: 2-3 weeks

### Phase 4: Polish & Scale (Week 13-16)
**Goal**: Professional polish, accessibility, expansion
1. Sprint 4 (animations, dark mode, voice, i18n, a11y)
2. Remaining enhancements (documents, OCR, communications)
3. Performance optimization
**Estimated**: 3-4 weeks

---

## SUCCESS METRICS

### Sprint 3 Targets
- [ ] Prior year import usage: >60% of returning users
- [ ] Contextual help reduces support tickets by >30%
- [ ] PDF preview increases filing confidence >35%

### Advisory Report Targets
- [ ] Generate report in <15 seconds
- [ ] CPA approval rate >95% (accuracy)
- [ ] User satisfaction >4.5/5 stars
- [ ] Report request rate >40% of all users
- [ ] Advisory upsell conversion >25%

### Business Impact Targets
- [ ] Average revenue per client: $50 → $500-2000 (10-40x)
- [ ] Client lifetime value: $150 → $5000+ (33x)
- [ ] Year-round engagement (not just tax season)
- [ ] CPA partner adoption >60%
- [ ] Break-even on development costs: 24 months

---

## DEPENDENCIES & RISKS

### Technical Dependencies
| Dependency | Purpose | Status |
|------------|---------|--------|
| ReportLab | PDF generation | ⬜ Need to install |
| Matplotlib | Charts/visualizations | ⬜ Need to install |
| Pillow | Watermarks/images | ⬜ Need to install |
| Google Places API | Address autocomplete | ⬜ Need API key |
| Web Speech API | Voice input | ✅ Browser native |

### Risk Mitigation
1. **Technical Complexity**: Start with MVP versions, iterate
2. **Legal Compliance**: Mandatory CPA review gates, comprehensive disclaimers
3. **User Adoption**: Phased rollout, A/B testing, user feedback loops
4. **Resource Constraints**: Prioritize highest ROI features first
5. **Tax Law Changes**: Build configurable rules engine, annual updates

---

## NEXT STEPS (IMMEDIATE ACTIONS)

### This Week
1. **Today**: Review this complete task list with stakeholders
2. **Tomorrow**: Prioritize Phase 1 (Sprint 3) vs Phase 2 (Advisory) first
3. **Day 3-5**: Begin implementation of chosen phase
4. **Weekend**: Team review of Week 1 progress

### Next Week
1. **Deploy Week 1 deliverables** to staging
2. **Begin Week 2 tasks**
3. **User testing** of completed features
4. **Iterate** based on feedback

### Month 1 Goal
- ✅ Sprint 3 complete and deployed
- ✅ Advisory Report Core 50% complete
- ✅ Entity Comparison live
- ✅ User metrics improved (satisfaction, completion rate)

---

## CONCLUSION

**Status**: All pending tasks have been identified, documented, and sequenced.

**Total Scope**:
- **25 discrete features** across 4 categories
- **35-50 days** of development work
- **$48,700** estimated budget
- **10-40x revenue potential** per client

**Readiness**: ✅ All backend infrastructure exists and is verified
**Design**: ✅ Complete specifications for all major features
**Sequence**: ✅ Clear 16-week phased roadmap
**ROI**: ✅ Projected break-even in 24 months, 10-40x revenue increase

**Ready to proceed with implementation.**

---

**Document Status**: ✅ COMPLETE
**Date**: 2026-01-21
**Version**: 1.0
**Next Action**: Stakeholder approval to begin Phase 1

---

## APPENDIX: REFERENCE DOCUMENTS

All detailed specifications available in:
- `/docs/MASTER_IMPLEMENTATION_ROADMAP.md` - Complete 16-week roadmap
- `/docs/VALUE_ADDITION_OPPORTUNITIES.md` - 6 designed features
- `/docs/ADVISORY_REPORT_QUICK_START.md` - Advisory implementation guide
- `/docs/ADVISORY_COMPUTATION_REPORT_DESIGN.md` - Report sections 1-2
- `/docs/ADVISORY_COMPUTATION_REPORT_SCENARIOS.md` - Report sections 3-5
- `/docs/ADVISORY_COMPUTATION_REPORT_IMPLEMENTATION.md` - Report sections 6-7
- `/docs/TAX_PROFESSIONAL_UNWRITTEN_WISDOM.md` - 70+ pages domain knowledge
- `/docs/PENDING_SPRINTS_AND_PHASES.md` - Original sprint planning
- `/docs/UI_BACKEND_AUDIT_REPORT.md` - Backend verification

**Total Documentation**: 400+ pages of specifications, designs, and implementation guides.