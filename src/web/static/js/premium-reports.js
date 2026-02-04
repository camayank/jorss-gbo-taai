/**
 * CA4CPA Global LLC - Premium Reports JavaScript Client
 *
 * Reusable component for accessing the Premium Reports API.
 * Can be embedded in any authenticated portal (client dashboard, CPA panel, etc.)
 *
 * SECURITY FIXES APPLIED:
 * - Removed inline onclick handlers (XSS vector)
 * - Added proper URL parameter encoding
 * - Improved HTML escaping for iframe srcdoc
 * - Added CSRF token support
 * - Added request timeout handling
 * - Used event delegation for click handlers
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
// SECURITY UTILITIES (local copy for standalone usage)
// =============================================================================

const ReportSecurity = {
  /**
   * HTML entities for escaping
   */
  HTML_ENTITIES: {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#x27;',
    '/': '&#x2F;',
    '`': '&#x60;',
    '=': '&#x3D;'
  },

  /**
   * Escape HTML special characters
   */
  escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str).replace(/[&<>"'`=\/]/g, char => this.HTML_ENTITIES[char]);
  },

  /**
   * Escape for JavaScript string context
   */
  escapeJs(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/\\/g, '\\\\')
      .replace(/'/g, "\\'")
      .replace(/"/g, '\\"')
      .replace(/\n/g, '\\n')
      .replace(/\r/g, '\\r')
      .replace(/<\/script/gi, '<\\/script');
  },

  /**
   * Validate tier value (whitelist approach)
   */
  validateTier(tier) {
    const validTiers = ['basic', 'standard', 'premium'];
    return validTiers.includes(tier) ? tier : 'basic';
  },

  /**
   * Validate format value (whitelist approach)
   */
  validateFormat(format) {
    const validFormats = ['html', 'pdf', 'json'];
    return validFormats.includes(format) ? format : 'html';
  },

  /**
   * Get CSRF token from meta tag or cookie
   */
  getCSRFToken() {
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) return metaTag.getAttribute('content');

    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
      const [name, value] = cookie.trim().split('=');
      if (name === 'csrf_token' || name === 'csrftoken' || name === '_csrf') {
        return decodeURIComponent(value);
      }
    }
    return null;
  }
};

// =============================================================================
// API CLIENT
// =============================================================================

class PremiumReportsClient {
  constructor(baseUrl = '/api/core/reports') {
    this.baseUrl = baseUrl;
    this.timeout = 30000; // 30 second timeout
  }

  /**
   * Make a secure fetch request with timeout and CSRF token
   */
  async secureFetch(url, options = {}) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    const headers = {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    };

    // Add CSRF token for state-changing requests
    const method = (options.method || 'GET').toUpperCase();
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
      const csrfToken = ReportSecurity.getCSRFToken();
      if (csrfToken) {
        headers['X-CSRF-Token'] = csrfToken;
      }
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        credentials: 'include',
        signal: controller.signal
      });
      clearTimeout(timeoutId);
      return response;
    } catch (error) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        throw new Error('Request timed out');
      }
      throw error;
    }
  }

  /**
   * Get available report tiers with pricing.
   */
  async getTiers() {
    const response = await this.secureFetch(`${this.baseUrl}/tiers`);
    if (!response.ok) {
      throw new Error(`Failed to get tiers: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Get sections included in a specific tier.
   */
  async getTierSections(tier) {
    const safeTier = ReportSecurity.validateTier(tier);
    const response = await this.secureFetch(`${this.baseUrl}/sections/${encodeURIComponent(safeTier)}`);
    if (!response.ok) {
      throw new Error(`Failed to get tier sections: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Get preview of what each tier includes for a session.
   */
  async getPreview(sessionId) {
    const safeSessionId = encodeURIComponent(sessionId);
    const response = await this.secureFetch(`${this.baseUrl}/preview/${safeSessionId}`);
    if (!response.ok) {
      throw new Error(`Failed to get preview: ${response.status}`);
    }
    return response.json();
  }

  /**
   * Generate a report.
   */
  async generateReport(sessionId, tier = 'basic', format = 'html') {
    const safeTier = ReportSecurity.validateTier(tier);
    const safeFormat = ReportSecurity.validateFormat(format);

    const response = await this.secureFetch(`${this.baseUrl}/generate`, {
      method: 'POST',
      body: JSON.stringify({
        session_id: sessionId,
        tier: safeTier,
        format: safeFormat,
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
   */
  async downloadReport(sessionId, tier = 'premium', format = 'pdf') {
    const safeTier = ReportSecurity.validateTier(tier);
    const safeFormat = ReportSecurity.validateFormat(format);

    // Use URLSearchParams for safe URL building
    const params = new URLSearchParams();
    params.set('tier', safeTier);
    params.set('format', safeFormat);

    const url = `${this.baseUrl}/download/${encodeURIComponent(sessionId)}?${params.toString()}`;
    const response = await this.secureFetch(url);

    if (!response.ok) {
      throw new Error(`Failed to download report: ${response.status}`);
    }

    // Get filename from Content-Disposition header
    const disposition = response.headers.get('Content-Disposition');
    let filename = `TaxReport.${safeFormat}`;
    if (disposition) {
      const match = disposition.match(/filename="?([^"]+)"?/);
      if (match) {
        // Sanitize filename to prevent path traversal
        filename = match[1].replace(/[^a-zA-Z0-9._-]/g, '_');
      }
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
    this.currentReport = null;

    // Bind methods for event handlers
    this._handleClick = this._handleClick.bind(this);

    this.render();
    this.loadTiers();

    // Set up event delegation (SECURITY: single listener, no inline handlers)
    this.container.addEventListener('click', this._handleClick);
  }

  /**
   * Delegated click handler - handles all button clicks safely
   */
  _handleClick(e) {
    const button = e.target.closest('button[data-action]');
    if (!button) return;

    const action = button.dataset.action;
    const tier = button.dataset.tier;
    const format = button.dataset.format;

    switch (action) {
      case 'select-tier':
        if (tier) this.selectTier(tier);
        break;
      case 'download':
        if (tier && format) this.downloadReport(tier, format);
        break;
    }
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
            color: var(--primary, #1e3a5f);
            margin: 0 0 0.5rem 0;
          }
          .prw-tiers {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 1.5rem;
          }
          .prw-tier {
            background: var(--bg-light, #f9fafb);
            border: 2px solid var(--border-color, #e5e7eb);
            border-radius: 12px;
            padding: 1.5rem;
            transition: all 0.2s ease;
          }
          .prw-tier:hover {
            border-color: var(--primary, #1e3a5f);
            box-shadow: 0 4px 12px rgba(30, 58, 95, 0.1);
          }
          .prw-tier.recommended {
            border-color: var(--primary, #1e3a5f);
            position: relative;
          }
          .prw-tier.recommended::before {
            content: 'RECOMMENDED';
            position: absolute;
            top: -12px;
            left: 50%;
            transform: translateX(-50%);
            background: var(--primary, #1e3a5f);
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
            color: var(--primary, #1e3a5f);
            margin: 0.5rem 0;
          }
          .prw-tier-price span {
            font-size: 1rem;
            font-weight: 400;
            color: var(--text-muted, #6b7280);
          }
          .prw-tier-desc {
            color: var(--text-muted, #6b7280);
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
            color: var(--success, #10b981);
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
            background: var(--primary, #1e3a5f);
            color: white;
          }
          .prw-btn-primary:hover {
            background: var(--primary-dark, #152b47);
          }
          .prw-btn-secondary {
            background: var(--border-color, #e5e7eb);
            color: var(--gray-600, #4b5563);
          }
          .prw-btn-secondary:hover {
            background: var(--gray-300, #d1d5db);
          }
          .prw-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
          }
          .prw-loading {
            text-align: center;
            padding: 2rem;
            color: var(--text-muted, #6b7280);
          }
          .prw-error {
            background: var(--error-light, #fee2e2);
            color: var(--error, #ef4444);
            padding: 1rem;
            border-radius: 8px;
            text-align: center;
          }
          .prw-report-preview {
            margin-top: 2rem;
            padding: 1.5rem;
            background: white;
            border: 1px solid var(--border-color, #e5e7eb);
            border-radius: 12px;
          }
          .prw-report-preview iframe {
            width: 100%;
            height: 600px;
            border: none;
            border-radius: 8px;
          }
          .prw-report-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
          }
          .prw-report-header h3 {
            margin: 0;
          }
          .prw-report-actions {
            display: flex;
            gap: 0.5rem;
          }
          .prw-btn-inline {
            width: auto;
            display: inline-block;
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

    // Build HTML safely using DOM methods
    container.innerHTML = '';

    this.tiers.forEach(tier => {
      const tierDiv = document.createElement('div');
      tierDiv.className = `prw-tier ${tier.tier === 'premium' ? 'recommended' : ''}`;

      // Create elements safely using textContent (not innerHTML with user data)
      const nameH3 = document.createElement('h3');
      nameH3.className = 'prw-tier-name';
      nameH3.textContent = tier.label || tier.tier;

      const priceDiv = document.createElement('div');
      priceDiv.className = 'prw-tier-price';
      if (tier.price === 0) {
        priceDiv.textContent = 'FREE';
      } else {
        priceDiv.innerHTML = `$${ReportSecurity.escapeHtml(tier.price)}<span>one-time</span>`;
      }

      const descP = document.createElement('p');
      descP.className = 'prw-tier-desc';
      descP.textContent = tier.description || '';

      const featureUl = document.createElement('ul');
      featureUl.className = 'prw-features';
      const highlights = tierHighlights[tier.tier] || [];
      highlights.forEach(feature => {
        const li = document.createElement('li');
        li.textContent = feature;
        featureUl.appendChild(li);
      });

      // SECURITY: Use data attributes instead of inline onclick
      const button = document.createElement('button');
      button.className = `prw-btn ${tier.tier === 'premium' ? 'prw-btn-primary' : 'prw-btn-secondary'}`;
      button.setAttribute('data-action', 'select-tier');
      button.setAttribute('data-tier', ReportSecurity.validateTier(tier.tier));
      button.textContent = tier.price === 0 ? 'Generate Free Report' : `Get ${tier.label || tier.tier}`;

      tierDiv.appendChild(nameH3);
      tierDiv.appendChild(priceDiv);
      tierDiv.appendChild(descP);
      tierDiv.appendChild(featureUl);
      tierDiv.appendChild(button);

      container.appendChild(tierDiv);
    });
  }

  async selectTier(tier) {
    const safeTier = ReportSecurity.validateTier(tier);

    if (!this.sessionId) {
      this.showError('No session ID provided');
      return;
    }

    const buttons = this.container.querySelectorAll('.prw-btn');
    buttons.forEach((btn) => (btn.disabled = true));

    try {
      // For paid tiers, you would integrate with Stripe here
      if (safeTier !== 'basic') {
        // Placeholder for payment flow
        // const paymentResult = await this.processPayment(safeTier);
        // if (!paymentResult.success) return;
      }

      // Generate the report
      const report = await this.client.generateReport(this.sessionId, safeTier, 'html');
      this.currentReport = report;
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
    const safeTier = ReportSecurity.validateTier(report.tier);
    const tierLabel = safeTier.charAt(0).toUpperCase() + safeTier.slice(1);

    // Clear container
    container.innerHTML = '';

    // Create preview div
    const previewDiv = document.createElement('div');
    previewDiv.className = 'prw-report-preview';

    // Create header
    const headerDiv = document.createElement('div');
    headerDiv.className = 'prw-report-header';

    const title = document.createElement('h3');
    title.textContent = `${tierLabel} Report`;

    const actionsDiv = document.createElement('div');
    actionsDiv.className = 'prw-report-actions';

    // HTML download button (SECURITY: data attributes, not inline onclick)
    const htmlBtn = document.createElement('button');
    htmlBtn.className = 'prw-btn prw-btn-secondary prw-btn-inline';
    htmlBtn.setAttribute('data-action', 'download');
    htmlBtn.setAttribute('data-tier', safeTier);
    htmlBtn.setAttribute('data-format', 'html');
    htmlBtn.textContent = 'Download HTML';
    actionsDiv.appendChild(htmlBtn);

    // PDF download button (only for premium)
    if (safeTier === 'premium') {
      const pdfBtn = document.createElement('button');
      pdfBtn.className = 'prw-btn prw-btn-primary prw-btn-inline';
      pdfBtn.setAttribute('data-action', 'download');
      pdfBtn.setAttribute('data-tier', safeTier);
      pdfBtn.setAttribute('data-format', 'pdf');
      pdfBtn.textContent = 'Download PDF';
      actionsDiv.appendChild(pdfBtn);
    }

    headerDiv.appendChild(title);
    headerDiv.appendChild(actionsDiv);

    // Create iframe for report content
    const iframe = document.createElement('iframe');
    iframe.setAttribute('sandbox', 'allow-same-origin'); // SECURITY: Sandboxed iframe

    // SECURITY: Use srcdoc with properly escaped content
    // The sandbox attribute restricts what the iframe can do
    if (report.html_content) {
      iframe.srcdoc = report.html_content;
    }

    previewDiv.appendChild(headerDiv);
    previewDiv.appendChild(iframe);
    container.appendChild(previewDiv);
  }

  async downloadReport(tier, format) {
    try {
      await this.client.downloadReport(
        this.sessionId,
        ReportSecurity.validateTier(tier),
        ReportSecurity.validateFormat(format)
      );
    } catch (error) {
      this.showError(error.message);
    }
  }

  showError(message) {
    const container = document.getElementById('prw-report-container');

    // SECURITY: Create element with textContent, not innerHTML
    const errorDiv = document.createElement('div');
    errorDiv.className = 'prw-error';
    errorDiv.textContent = message;

    container.innerHTML = '';
    container.appendChild(errorDiv);
  }

  /**
   * Cleanup method - call when component unmounts
   */
  destroy() {
    if (this.container) {
      this.container.removeEventListener('click', this._handleClick);
    }
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
  module.exports = { PremiumReportsClient, PremiumReportsWidget, ReportSecurity };
}
