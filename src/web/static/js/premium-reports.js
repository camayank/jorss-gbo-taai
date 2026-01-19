/**
 * CA4CPA Global LLC - Premium Reports JavaScript Client
 *
 * Reusable component for accessing the Premium Reports API.
 * Can be embedded in any authenticated portal (client dashboard, CPA panel, etc.)
 *
 * Usage:
 *   <script src="/static/js/premium-reports.js"></script>
 *   <div id="premium-reports-widget" data-session-id="abc123"></div>
 *
 * Or programmatically:
 *   const client = new PremiumReportsClient('/api/core/reports');
 *   const report = await client.generateReport(sessionId, 'premium', 'html');
 */

// =============================================================================
// API CLIENT
// =============================================================================

class PremiumReportsClient {
  constructor(baseUrl = '/api/core/reports') {
    this.baseUrl = baseUrl;
  }

  /**
   * Get available report tiers with pricing.
   * @returns {Promise<Array>} List of tier objects
   */
  async getTiers() {
    const response = await fetch(`${this.baseUrl}/tiers`, {
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) {
      throw new Error(`Failed to get tiers: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Get sections included in a specific tier.
   * @param {string} tier - 'basic', 'standard', or 'premium'
   * @returns {Promise<Object>} Tier sections info
   */
  async getTierSections(tier) {
    const response = await fetch(`${this.baseUrl}/sections/${tier}`, {
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) {
      throw new Error(`Failed to get tier sections: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Get preview of what each tier includes for a session.
   * @param {string} sessionId - Tax calculation session ID
   * @returns {Promise<Object>} Preview data
   */
  async getPreview(sessionId) {
    const response = await fetch(`${this.baseUrl}/preview/${sessionId}`, {
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!response.ok) {
      throw new Error(`Failed to get preview: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Generate a report.
   * @param {string} sessionId - Tax calculation session ID
   * @param {string} tier - 'basic', 'standard', or 'premium'
   * @param {string} format - 'html', 'pdf', or 'json'
   * @returns {Promise<Object>} Generated report
   */
  async generateReport(sessionId, tier = 'basic', format = 'html') {
    const response = await fetch(`${this.baseUrl}/generate`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: sessionId,
        tier: tier,
        format: format,
      }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `Failed to generate report: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Download a report as a file.
   * @param {string} sessionId - Tax calculation session ID
   * @param {string} tier - 'basic', 'standard', or 'premium'
   * @param {string} format - 'html', 'pdf', or 'json'
   */
  async downloadReport(sessionId, tier = 'premium', format = 'pdf') {
    const url = `${this.baseUrl}/download/${sessionId}?tier=${tier}&format=${format}`;
    const response = await fetch(url, {
      credentials: 'include',
    });
    if (!response.ok) {
      throw new Error(`Failed to download report: ${response.status}`);
    }

    // Get filename from Content-Disposition header
    const disposition = response.headers.get('Content-Disposition');
    let filename = `TaxReport.${format}`;
    if (disposition) {
      const match = disposition.match(/filename="(.+)"/);
      if (match) filename = match[1];
    }

    // Download file
    const blob = await response.blob();
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
  }
}

// =============================================================================
// UI WIDGET
// =============================================================================

class PremiumReportsWidget {
  constructor(containerId, options = {}) {
    this.container = document.getElementById(containerId);
    if (!this.container) {
      console.error(`Container #${containerId} not found`);
      return;
    }

    this.sessionId = options.sessionId || this.container.dataset.sessionId;
    this.client = new PremiumReportsClient(options.baseUrl);
    this.onReportGenerated = options.onReportGenerated || (() => {});

    this.render();
    this.loadTiers();
  }

  async loadTiers() {
    try {
      this.tiers = await this.client.getTiers();
      this.renderTiers();
    } catch (error) {
      console.error('Failed to load tiers:', error);
      this.showError('Failed to load pricing information');
    }
  }

  render() {
    this.container.innerHTML = `
      <div class="premium-reports-widget">
        <style>
          .premium-reports-widget {
            font-family: system-ui, -apple-system, sans-serif;
            max-width: 900px;
          }
          .prw-header {
            text-align: center;
            margin-bottom: 2rem;
          }
          .prw-header h2 {
            color: #4f46e5;
            margin: 0 0 0.5rem 0;
          }
          .prw-tiers {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 1.5rem;
          }
          .prw-tier {
            background: #f8fafc;
            border: 2px solid #e2e8f0;
            border-radius: 12px;
            padding: 1.5rem;
            transition: all 0.2s ease;
          }
          .prw-tier:hover {
            border-color: #6366f1;
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.1);
          }
          .prw-tier.recommended {
            border-color: #6366f1;
            position: relative;
          }
          .prw-tier.recommended::before {
            content: 'RECOMMENDED';
            position: absolute;
            top: -12px;
            left: 50%;
            transform: translateX(-50%);
            background: #6366f1;
            color: white;
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
          }
          .prw-tier-name {
            font-size: 1.25rem;
            font-weight: 600;
            margin: 0 0 0.25rem 0;
          }
          .prw-tier-price {
            font-size: 2rem;
            font-weight: 700;
            color: #6366f1;
            margin: 0.5rem 0;
          }
          .prw-tier-price span {
            font-size: 1rem;
            font-weight: 400;
            color: #64748b;
          }
          .prw-tier-desc {
            color: #64748b;
            margin-bottom: 1rem;
            font-size: 0.9rem;
          }
          .prw-features {
            list-style: none;
            padding: 0;
            margin: 0 0 1rem 0;
          }
          .prw-features li {
            padding: 0.5rem 0;
            border-bottom: 1px solid #e2e8f0;
            font-size: 0.9rem;
          }
          .prw-features li:last-child {
            border-bottom: none;
          }
          .prw-features li::before {
            content: '\\2713';
            color: #10b981;
            margin-right: 0.5rem;
            font-weight: bold;
          }
          .prw-btn {
            display: block;
            width: 100%;
            padding: 0.75rem 1rem;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
          }
          .prw-btn-primary {
            background: #6366f1;
            color: white;
          }
          .prw-btn-primary:hover {
            background: #4f46e5;
          }
          .prw-btn-secondary {
            background: #e2e8f0;
            color: #475569;
          }
          .prw-btn-secondary:hover {
            background: #cbd5e1;
          }
          .prw-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }
          .prw-loading {
            text-align: center;
            padding: 2rem;
            color: #64748b;
          }
          .prw-error {
            background: #fef2f2;
            color: #dc2626;
            padding: 1rem;
            border-radius: 8px;
            text-align: center;
          }
          .prw-report-preview {
            margin-top: 2rem;
            padding: 1.5rem;
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
          }
          .prw-report-preview iframe {
            width: 100%;
            height: 600px;
            border: none;
            border-radius: 8px;
          }
        </style>

        <div class="prw-header">
          <h2>Tax Advisory Reports</h2>
          <p>Get personalized insights and recommendations</p>
        </div>

        <div class="prw-tiers" id="prw-tiers">
          <div class="prw-loading">Loading pricing...</div>
        </div>

        <div id="prw-report-container"></div>
      </div>
    `;
  }

  renderTiers() {
    const container = document.getElementById('prw-tiers');
    if (!this.tiers || this.tiers.length === 0) {
      container.innerHTML = '<div class="prw-error">No tiers available</div>';
      return;
    }

    const tierHighlights = {
      basic: ['Tax calculation summary', 'Draft Form 1040 preview', 'Computation statement'],
      standard: [
        'Everything in Basic',
        'Credit eligibility analysis',
        'Deduction optimization',
        'What-if scenarios',
        'Retirement strategy',
      ],
      premium: [
        'Everything in Standard',
        'Prioritized action items',
        'Multi-year projection',
        'Investment tax planning',
        'Full IRC citations',
        'Downloadable PDF',
      ],
    };

    container.innerHTML = this.tiers
      .map(
        (tier) => `
      <div class="prw-tier ${tier.tier === 'premium' ? 'recommended' : ''}">
        <h3 class="prw-tier-name">${tier.label}</h3>
        <div class="prw-tier-price">
          ${tier.price === 0 ? 'FREE' : `$${tier.price}`}
          ${tier.price > 0 ? '<span>one-time</span>' : ''}
        </div>
        <p class="prw-tier-desc">${tier.description}</p>
        <ul class="prw-features">
          ${(tierHighlights[tier.tier] || []).map((f) => `<li>${f}</li>`).join('')}
        </ul>
        <button
          class="prw-btn ${tier.tier === 'premium' ? 'prw-btn-primary' : 'prw-btn-secondary'}"
          onclick="premiumReportsWidget.selectTier('${tier.tier}')"
        >
          ${tier.price === 0 ? 'Generate Free Report' : `Get ${tier.label}`}
        </button>
      </div>
    `
      )
      .join('');
  }

  async selectTier(tier) {
    if (!this.sessionId) {
      this.showError('No session ID provided');
      return;
    }

    const buttons = this.container.querySelectorAll('.prw-btn');
    buttons.forEach((btn) => (btn.disabled = true));

    try {
      // For paid tiers, you would integrate with Stripe here
      if (tier !== 'basic') {
        // Placeholder for payment flow
        // const paymentResult = await this.processPayment(tier);
        // if (!paymentResult.success) return;
      }

      // Generate the report
      const report = await this.client.generateReport(this.sessionId, tier, 'html');
      this.showReport(report);
      this.onReportGenerated(report);
    } catch (error) {
      console.error('Report generation failed:', error);
      this.showError(error.message);
    } finally {
      buttons.forEach((btn) => (btn.disabled = false));
    }
  }

  showReport(report) {
    const container = document.getElementById('prw-report-container');
    container.innerHTML = `
      <div class="prw-report-preview">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
          <h3 style="margin: 0;">${report.tier.charAt(0).toUpperCase() + report.tier.slice(1)} Report</h3>
          <div>
            <button class="prw-btn prw-btn-secondary" style="width: auto; display: inline-block; margin-right: 0.5rem;"
              onclick="premiumReportsWidget.downloadReport('${report.tier}', 'html')">
              Download HTML
            </button>
            ${
              report.tier === 'premium'
                ? `
              <button class="prw-btn prw-btn-primary" style="width: auto; display: inline-block;"
                onclick="premiumReportsWidget.downloadReport('${report.tier}', 'pdf')">
                Download PDF
              </button>
            `
                : ''
            }
          </div>
        </div>
        <iframe srcdoc="${this.escapeHtml(report.html_content)}"></iframe>
      </div>
    `;
  }

  async downloadReport(tier, format) {
    try {
      await this.client.downloadReport(this.sessionId, tier, format);
    } catch (error) {
      this.showError(error.message);
    }
  }

  showError(message) {
    const container = document.getElementById('prw-report-container');
    container.innerHTML = `<div class="prw-error">${this.escapeHtml(message)}</div>`;
  }

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/"/g, '&quot;');
  }
}

// =============================================================================
// AUTO-INIT
// =============================================================================

// Auto-initialize widget if data attribute is present
document.addEventListener('DOMContentLoaded', () => {
  const widgetContainer = document.getElementById('premium-reports-widget');
  if (widgetContainer) {
    window.premiumReportsWidget = new PremiumReportsWidget('premium-reports-widget');
  }
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { PremiumReportsClient, PremiumReportsWidget };
}
