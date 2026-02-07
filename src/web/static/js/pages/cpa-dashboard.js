/**
 * CPA Dashboard Page JavaScript
 *
 * Imports core utilities from modular system.
 * Contains CPA-specific business logic.
 */

// Import core utilities
import {
  escapeHtml,
  formatCurrency,
  formatNumber,
  getInitials,
  formatRelativeTime,
  debounce,
  showToast,
  showLoading,
  hideLoading,
} from '/static/js/core/utils.js';

import { api, getCsrfToken } from '/static/js/core/api.js';

// =============================================================================
// APPLICATION STATE
// =============================================================================
const state = {
  currentView: 'dashboard',
  insights: [],
  clients: [],
  leads: [],
  selectedInsight: null,
  preparerId: null,
  totals: { savings: 0, implemented: 0, pending: 0 },
  categories: { retirement: 0, deductions: 0, credits: 0, qbi: 0, investment: 0 },
};

// Core Platform API Base
const CORE_API = '/api/core';

// =============================================================================
// MOBILE NAVIGATION
// =============================================================================
export function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  const hamburger = document.getElementById('hamburger-btn');

  if (!sidebar) return;

  const isOpen = sidebar.classList.contains('open');

  if (isOpen) {
    sidebar.classList.remove('open');
    overlay?.classList.remove('active');
    hamburger?.classList.remove('active');
    document.body.style.overflow = '';
  } else {
    sidebar.classList.add('open');
    overlay?.classList.add('active');
    hamburger?.classList.add('active');
    document.body.style.overflow = 'hidden';
  }
}

// =============================================================================
// VIEW SWITCHING
// =============================================================================
export function switchView(viewName) {
  // Update state
  state.currentView = viewName;

  // Hide all views
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));

  // Show target view
  const targetView = document.getElementById(`view-${viewName}`);
  if (targetView) {
    targetView.classList.add('active');
  }

  // Update nav items
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.view === viewName);
  });

  // Load view data
  loadViewData(viewName);

  // Close mobile sidebar if open
  if (window.innerWidth <= 1024) {
    const sidebar = document.getElementById('sidebar');
    if (sidebar?.classList.contains('open')) {
      toggleSidebar();
    }
  }
}

async function loadViewData(viewName) {
  switch (viewName) {
    case 'dashboard':
      await loadDashboardData();
      break;
    case 'insights':
      await loadInsightsData();
      break;
    case 'clients':
      await loadClientsData();
      break;
    case 'pipeline':
      await loadPipelineData();
      break;
    case 'review':
      await loadReviewData();
      break;
  }
}

// =============================================================================
// CORE API HELPER
// =============================================================================
export async function coreApi(endpoint, options = {}) {
  const token = localStorage.getItem('cpa_token') || state.preparerId;
  const headers = {
    'Content-Type': 'application/json',
    ...(token && { 'Authorization': `Bearer ${token}` }),
    ...(state.preparerId && { 'X-Preparer-ID': state.preparerId }),
  };

  // Add CSRF token for state-changing requests
  const method = (options.method || 'GET').toUpperCase();
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    const csrfToken = getCsrfToken();
    if (csrfToken) {
      headers['X-CSRF-Token'] = csrfToken;
    }
  }

  try {
    const response = await fetch(`${CORE_API}${endpoint}`, {
      ...options,
      headers: { ...headers, ...(options.headers || {}) },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Request failed: ${response.status}`);
    }

    return await response.json();
  } catch (e) {
    console.error(`Core API Error: ${endpoint}`, e);
    return { success: false, error: e.message };
  }
}

// =============================================================================
// DASHBOARD DATA LOADING
// =============================================================================
export async function loadDashboardData() {
  showSkeleton('top-insights', 3);
  showSkeleton('high-value-clients', 3);

  try {
    // Load insights and clients in parallel
    const [insightsData, clientsData] = await Promise.all([
      api('/api/cpa/insights', { timeout: 10000 }),
      api('/api/cpa/clients', { timeout: 10000 }),
    ]);

    if (insightsData.insights) {
      state.insights = insightsData.insights;
      renderTopInsights(insightsData.insights.slice(0, 5));
      updateCategoryStats(insightsData.insights);
    }

    if (clientsData.clients) {
      state.clients = clientsData.clients;
      renderHighValueClients(clientsData.clients.slice(0, 5));
    }

    // Update dashboard stats
    updateDashboardStats();
  } catch (e) {
    console.error('Dashboard load error:', e);
    showEmptyState('top-insights', 'Could not load insights');
    showEmptyState('high-value-clients', 'Could not load clients');
  }
}

// =============================================================================
// RENDERING FUNCTIONS
// =============================================================================
function renderTopInsights(insights) {
  const container = document.getElementById('top-insights');
  if (!container) return;

  if (!insights.length) {
    showEmptyState(container, 'No insights available');
    return;
  }

  container.innerHTML = insights.map(insight => `
    <div class="insight-item" onclick="openInsightDetail('${escapeHtml(insight.id)}')">
      <div class="insight-icon ${getInsightIconClass(insight.type)}">
        ${getInsightIcon(insight.type)}
      </div>
      <div class="insight-content">
        <div class="insight-title">${escapeHtml(insight.title)}</div>
        <div class="insight-desc">${escapeHtml(insight.description)}</div>
        <div class="insight-meta">
          ${insight.irs_reference ? `<span class="insight-tag irs">${escapeHtml(insight.irs_reference)}</span>` : ''}
          <span class="insight-tag">${escapeHtml(insight.category)}</span>
        </div>
      </div>
      <div class="insight-amount">${formatCurrency(insight.potential_savings)}</div>
    </div>
  `).join('');
}

function renderHighValueClients(clients) {
  const container = document.getElementById('high-value-clients');
  if (!container) return;

  if (!clients.length) {
    showEmptyState(container, 'No clients yet');
    return;
  }

  container.innerHTML = clients.map(client => `
    <div class="client-row" onclick="openClientDetail('${escapeHtml(client.id || client.session_id)}')">
      <div class="client-avatar">${getInitials(client.name)}</div>
      <div class="client-info">
        <div class="client-name">${escapeHtml(client.name)}</div>
        <div class="client-detail">${escapeHtml(client.email || 'No email')}</div>
      </div>
      <div class="client-savings">
        <div class="savings-amount">${formatCurrency(client.potential_savings || 0)}</div>
        <div class="savings-label">potential</div>
      </div>
    </div>
  `).join('');
}

function updateCategoryStats(insights) {
  const categories = { retirement: 0, deductions: 0, credits: 0, qbi: 0, investment: 0 };

  insights.forEach(insight => {
    const cat = insight.category?.toLowerCase();
    if (cat && categories.hasOwnProperty(cat)) {
      categories[cat]++;
    }
  });

  Object.entries(categories).forEach(([cat, count]) => {
    const countEl = document.getElementById(`opt-${cat}-count`);
    const levelEl = document.getElementById(`opt-${cat}-level`);
    if (countEl) countEl.textContent = count;
    if (levelEl) levelEl.textContent = count > 5 ? 'High' : count > 2 ? 'Medium' : count > 0 ? 'Low' : '—';
  });

  state.categories = categories;
}

function updateDashboardStats() {
  const totalSavings = state.insights.reduce((sum, i) => sum + (i.potential_savings || 0), 0);
  const highLeverage = state.insights.filter(i => (i.potential_savings || 0) > 5000).length;
  const needsReview = state.insights.filter(i => !i.reviewed).length;
  const complexCases = state.clients.filter(c => c.complexity === 'high').length;

  animateNumber('stat-high-leverage', highLeverage);
  animateNumber('stat-needs-review', needsReview);
  animateNumber('stat-complexity', complexCases);
  animateNumber('leads-ready-count', state.clients.length);

  // Update advisory surface level
  const surfaceEl = document.getElementById('advisory-surface-level');
  if (surfaceEl) {
    surfaceEl.textContent = totalSavings > 100000 ? 'High Opportunity' :
                            totalSavings > 50000 ? 'Medium Opportunity' :
                            totalSavings > 0 ? 'Some Opportunities' : 'Analyzing...';
  }
}

// =============================================================================
// UTILITY FUNCTIONS
// =============================================================================
function getInsightIconClass(type) {
  const classes = {
    savings: 'savings',
    warning: 'warning',
    critical: 'critical',
    info: 'info',
  };
  return classes[type] || 'info';
}

function getInsightIcon(type) {
  const icons = {
    savings: '$',
    warning: '!',
    critical: '!',
    info: 'i',
  };
  return icons[type] || 'i';
}

function showSkeleton(containerId, count = 3) {
  const container = document.getElementById(containerId);
  if (!container) return;

  let html = '';
  for (let i = 0; i < count; i++) {
    html += `
      <div style="padding:16px;border-bottom:1px solid var(--color-gray-100)">
        <div class="skeleton skeleton-text" style="width:60%"></div>
        <div class="skeleton skeleton-text sm" style="width:80%"></div>
        <div class="skeleton skeleton-text sm" style="width:40%"></div>
      </div>
    `;
  }
  container.innerHTML = html;
}

function showEmptyState(container, message) {
  const el = typeof container === 'string' ? document.getElementById(container) : container;
  if (!el) return;

  el.innerHTML = `
    <div class="empty-state">
      <div class="empty-icon">—</div>
      <div class="empty-title">${escapeHtml(message)}</div>
    </div>
  `;
}

function animateNumber(elementId, targetValue, duration = 1000) {
  const element = document.getElementById(elementId);
  if (!element) return;

  const startValue = 0;
  const startTime = performance.now();

  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const easeProgress = 1 - Math.pow(1 - progress, 3);
    const currentValue = Math.floor(startValue + (targetValue - startValue) * easeProgress);

    element.textContent = currentValue.toLocaleString();

    if (progress < 1) {
      requestAnimationFrame(update);
    } else {
      element.textContent = targetValue.toLocaleString();
    }
  }

  requestAnimationFrame(update);
}

// =============================================================================
// INSIGHTS VIEW
// =============================================================================
async function loadInsightsData() {
  const container = document.getElementById('insights-list');
  if (!container) return;

  showSkeleton('insights-list', 5);

  try {
    const data = await api.get('/api/cpa/insights');
    if (data.insights) {
      state.insights = data.insights;
      renderInsightsList(data.insights);
      updateInsightsBadge(data.insights.length);
    }
  } catch (e) {
    showEmptyState('insights-list', 'Could not load insights');
  }
}

function renderInsightsList(insights) {
  const container = document.getElementById('insights-list');
  if (!container) return;

  if (!insights.length) {
    showEmptyState(container, 'No insights available');
    return;
  }

  container.innerHTML = insights.map(insight => `
    <div class="insight-item" onclick="openInsightDetail('${escapeHtml(insight.id)}')">
      <div class="insight-icon ${getInsightIconClass(insight.type)}">
        ${getInsightIcon(insight.type)}
      </div>
      <div class="insight-content">
        <div class="insight-title">${escapeHtml(insight.title)}</div>
        <div class="insight-desc">${escapeHtml(insight.description)}</div>
        <div class="insight-meta">
          ${insight.irs_reference ? `<span class="insight-tag irs">${escapeHtml(insight.irs_reference)}</span>` : ''}
          <span class="insight-tag">${escapeHtml(insight.category)}</span>
        </div>
      </div>
      <div class="insight-amount">${formatCurrency(insight.potential_savings)}</div>
    </div>
  `).join('');
}

function updateInsightsBadge(count) {
  const badge = document.getElementById('insights-badge');
  if (badge) {
    badge.textContent = count;
    badge.setAttribute('aria-label', `${count} signals`);
  }
}

// =============================================================================
// CLIENTS VIEW
// =============================================================================
async function loadClientsData() {
  const container = document.getElementById('clients-list');
  if (!container) return;

  showSkeleton('clients-list', 5);

  try {
    const data = await api.get('/api/cpa/clients');
    if (data.clients) {
      state.clients = data.clients;
      renderClientsList(data.clients);
    }
  } catch (e) {
    showEmptyState('clients-list', 'Could not load clients');
  }
}

function renderClientsList(clients) {
  const container = document.getElementById('clients-list');
  if (!container) return;

  if (!clients.length) {
    showEmptyState(container, 'No clients yet');
    return;
  }

  container.innerHTML = clients.map(client => `
    <div class="client-row" onclick="openClientDetail('${escapeHtml(client.id || client.session_id)}')">
      <div class="client-avatar">${getInitials(client.name)}</div>
      <div class="client-info">
        <div class="client-name">${escapeHtml(client.name)}</div>
        <div class="client-detail">${escapeHtml(client.email || 'No email')} | ${escapeHtml(client.status || 'Active')}</div>
      </div>
      <div class="client-savings">
        <div class="savings-amount">${formatCurrency(client.potential_savings || 0)}</div>
        <div class="savings-label">potential savings</div>
      </div>
    </div>
  `).join('');
}

// =============================================================================
// PIPELINE VIEW
// =============================================================================
async function loadPipelineData() {
  try {
    const data = await api.get('/api/cpa/pipeline');
    if (data.leads) {
      state.leads = data.leads;
      renderPipeline(data.leads);
      updatePipelineBadge(data.leads.length);
    }
  } catch (e) {
    console.error('Pipeline load error:', e);
  }
}

function renderPipeline(leads) {
  const stages = ['new', 'contacted', 'qualified', 'engaged'];

  stages.forEach(stage => {
    const column = document.getElementById(`pipeline-${stage}`);
    if (!column) return;

    const stageLeads = leads.filter(l => l.stage === stage);
    const countEl = column.querySelector('.pipeline-column-count');
    if (countEl) countEl.textContent = stageLeads.length;

    const cardsContainer = column.querySelector('.pipeline-cards');
    if (cardsContainer) {
      cardsContainer.innerHTML = stageLeads.map(lead => `
        <div class="pipeline-card ${lead.value === 'high' ? 'high-value' : ''}"
             onclick="openLeadDetail('${escapeHtml(lead.id)}')">
          <div class="client-name">${escapeHtml(lead.name)}</div>
          <div class="client-detail">${escapeHtml(lead.source || 'Direct')}</div>
          ${lead.potential_savings ? `<div class="savings-amount" style="margin-top:8px">${formatCurrency(lead.potential_savings)}</div>` : ''}
        </div>
      `).join('');
    }
  });
}

function updatePipelineBadge(count) {
  const badge = document.getElementById('pipeline-badge');
  if (badge) {
    badge.textContent = count;
    badge.setAttribute('aria-label', `${count} leads`);
  }
}

// =============================================================================
// REVIEW VIEW
// =============================================================================
async function loadReviewData() {
  try {
    const data = await api.get('/api/cpa/review-queue');
    if (data.items) {
      renderReviewQueue(data.items);
      updateReviewBadge(data.items.length);
    }
  } catch (e) {
    console.error('Review queue load error:', e);
  }
}

function renderReviewQueue(items) {
  const container = document.getElementById('review-queue-list');
  if (!container) return;

  if (!items.length) {
    showEmptyState(container, 'No items pending review');
    return;
  }

  container.innerHTML = items.map(item => `
    <div class="client-row" onclick="openReviewItem('${escapeHtml(item.id)}')">
      <div class="client-avatar" style="background:var(--color-warning-100);color:var(--color-warning-700)">!</div>
      <div class="client-info">
        <div class="client-name">${escapeHtml(item.client_name)}</div>
        <div class="client-detail">${escapeHtml(item.type)} | ${formatRelativeTime(item.submitted_at)}</div>
      </div>
      <div>
        <span class="insight-tag ${item.priority === 'high' ? 'alert' : ''}">${escapeHtml(item.priority || 'normal')}</span>
      </div>
    </div>
  `).join('');
}

function updateReviewBadge(count) {
  const badge = document.getElementById('review-badge');
  if (badge) {
    badge.textContent = count;
    badge.setAttribute('aria-label', `${count} items`);
  }
}

// =============================================================================
// DETAIL PANELS
// =============================================================================
export function openInsightDetail(insightId) {
  const insight = state.insights.find(i => i.id === insightId);
  if (!insight) return;

  state.selectedInsight = insight;

  const panel = document.getElementById('insight-detail-panel');
  if (!panel) return;

  // Populate panel
  const titleEl = panel.querySelector('.panel-title');
  if (titleEl) titleEl.textContent = insight.title;

  const bodyEl = panel.querySelector('.panel-body');
  if (bodyEl) {
    bodyEl.innerHTML = `
      <div class="panel-section">
        <div class="panel-section-title">Description</div>
        <p style="color:var(--color-gray-700)">${escapeHtml(insight.description)}</p>
      </div>
      <div class="panel-section">
        <div class="panel-section-title">Potential Savings</div>
        <div style="font-size:32px;font-weight:700;color:var(--color-success-600)">${formatCurrency(insight.potential_savings)}</div>
      </div>
      ${insight.irs_reference ? `
        <div class="panel-section">
          <div class="panel-section-title">IRS Reference</div>
          <span class="irs-ref">${escapeHtml(insight.irs_reference)}</span>
        </div>
      ` : ''}
      ${insight.action_steps ? `
        <div class="panel-section">
          <div class="panel-section-title">Action Steps</div>
          ${insight.action_steps.map((step, i) => `
            <div class="action-step">
              <div class="step-number">${i + 1}</div>
              <div class="step-content">
                <div class="step-title">${escapeHtml(step.title)}</div>
                <div class="step-desc">${escapeHtml(step.description)}</div>
              </div>
            </div>
          `).join('')}
        </div>
      ` : ''}
    `;
  }

  panel.classList.add('active');
}

export function openClientDetail(clientId) {
  const client = state.clients.find(c => (c.id || c.session_id) === clientId);
  if (!client) return;

  const panel = document.getElementById('client-detail-panel');
  if (!panel) return;

  // Populate panel
  const titleEl = panel.querySelector('.panel-title');
  if (titleEl) titleEl.textContent = client.name;

  const bodyEl = panel.querySelector('.panel-body');
  if (bodyEl) {
    bodyEl.innerHTML = `
      <div class="panel-section">
        <div class="panel-section-title">Contact</div>
        <p style="color:var(--color-gray-700)">${escapeHtml(client.email || 'No email')}</p>
        <p style="color:var(--color-gray-500);font-size:13px">${escapeHtml(client.phone || 'No phone')}</p>
      </div>
      <div class="panel-section">
        <div class="panel-section-title">Potential Savings</div>
        <div style="font-size:32px;font-weight:700;color:var(--color-success-600)">${formatCurrency(client.potential_savings)}</div>
      </div>
      <div class="panel-section">
        <div class="panel-section-title">Status</div>
        <span class="insight-tag">${escapeHtml(client.status || 'Active')}</span>
      </div>
    `;
  }

  panel.classList.add('active');
}

export function closePanel() {
  document.querySelectorAll('.detail-panel').forEach(panel => {
    panel.classList.remove('active');
  });
}

// =============================================================================
// COMMAND PALETTE
// =============================================================================
const commandPaletteCommands = [
  { id: 'dashboard', title: 'Dashboard', desc: 'View overview and insights', action: () => switchView('dashboard') },
  { id: 'clients', title: 'Clients', desc: 'Manage all clients', action: () => switchView('clients') },
  { id: 'pipeline', title: 'Pipeline', desc: 'View lead pipeline', action: () => switchView('pipeline') },
  { id: 'insights', title: 'Insights', desc: 'CPA review signals', action: () => switchView('insights') },
  { id: 'review', title: 'Review Queue', desc: 'Returns pending review', action: () => switchView('review') },
  { id: 'refresh', title: 'Refresh Data', desc: 'Reload all data', action: () => refreshDashboard() },
];

export function openCommandPalette() {
  const backdrop = document.getElementById('command-palette-backdrop');
  const input = document.getElementById('command-palette-input');
  if (!backdrop || !input) return;

  backdrop.classList.add('active');
  input.value = '';
  input.focus();
  renderCommandPaletteResults('');
}

export function closeCommandPalette() {
  const backdrop = document.getElementById('command-palette-backdrop');
  if (backdrop) backdrop.classList.remove('active');
}

function renderCommandPaletteResults(query) {
  const container = document.getElementById('command-palette-results');
  if (!container) return;

  const q = query.toLowerCase().trim();

  // Filter commands
  const filteredCommands = commandPaletteCommands.filter(cmd =>
    cmd.title.toLowerCase().includes(q) || cmd.desc.toLowerCase().includes(q)
  );

  // Filter clients
  const filteredClients = (state.clients || [])
    .filter(c => c.name?.toLowerCase().includes(q) || c.email?.toLowerCase().includes(q))
    .slice(0, 5);

  let html = '';

  if (filteredCommands.length > 0) {
    html += '<div class="command-palette-section">Commands</div>';
    filteredCommands.forEach(cmd => {
      html += `
        <div class="command-palette-item" data-cmd="${cmd.id}">
          <div class="command-palette-item-icon">#</div>
          <div class="command-palette-item-content">
            <div class="command-palette-item-title">${escapeHtml(cmd.title)}</div>
            <div class="command-palette-item-desc">${escapeHtml(cmd.desc)}</div>
          </div>
        </div>
      `;
    });
  }

  if (q && filteredClients.length > 0) {
    html += '<div class="command-palette-section">Clients</div>';
    filteredClients.forEach(client => {
      html += `
        <div class="command-palette-item" data-client="${escapeHtml(client.id || client.session_id)}">
          <div class="command-palette-item-icon">${getInitials(client.name)}</div>
          <div class="command-palette-item-content">
            <div class="command-palette-item-title">${escapeHtml(client.name || 'Unknown')}</div>
            <div class="command-palette-item-desc">${escapeHtml(client.email || 'No email')}</div>
          </div>
        </div>
      `;
    });
  }

  if (!html) {
    html = '<div class="command-palette-empty">No results found</div>';
  }

  container.innerHTML = html;

  // Add click handlers
  container.querySelectorAll('[data-cmd]').forEach(item => {
    item.addEventListener('click', () => {
      const cmd = commandPaletteCommands.find(c => c.id === item.dataset.cmd);
      if (cmd) {
        closeCommandPalette();
        cmd.action();
      }
    });
  });

  container.querySelectorAll('[data-client]').forEach(item => {
    item.addEventListener('click', () => {
      closeCommandPalette();
      openClientDetail(item.dataset.client);
    });
  });
}

// =============================================================================
// REFRESH DATA
// =============================================================================
export async function refreshDashboard() {
  showToast('Refreshing data...', 'info');
  await loadDashboardData();
  showToast('Data refreshed', 'success');
}

export function refreshData() {
  refreshDashboard();
}

// =============================================================================
// FILTER BY CATEGORY
// =============================================================================
export function filterByCategory(category) {
  switchView('insights');
  // Could add category filter state here
}

// =============================================================================
// INITIALIZATION
// =============================================================================
function init() {
  // Set up keyboard shortcuts
  document.addEventListener('keydown', e => {
    // Escape - close panels/modals
    if (e.key === 'Escape') {
      const palette = document.getElementById('command-palette-backdrop');
      if (palette?.classList.contains('active')) {
        closeCommandPalette();
      } else {
        closePanel();
      }
    }

    // Ctrl/Cmd + K - open command palette
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
      e.preventDefault();
      openCommandPalette();
    }
  });

  // Command palette input handler
  const paletteInput = document.getElementById('command-palette-input');
  if (paletteInput) {
    paletteInput.addEventListener('input', debounce(e => {
      renderCommandPaletteResults(e.target.value);
    }, 150));
  }

  // Close sidebar on nav item click (mobile)
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
      if (window.innerWidth <= 1024) {
        const sidebar = document.getElementById('sidebar');
        if (sidebar?.classList.contains('open')) {
          toggleSidebar();
        }
      }
    });
  });

  // Close sidebar on window resize
  window.addEventListener('resize', () => {
    const sidebar = document.getElementById('sidebar');
    if (window.innerWidth > 1024 && sidebar?.classList.contains('open')) {
      toggleSidebar();
    }
  });

  // Load initial data
  loadDashboardData();
}

// Export state for use in template
export { state };

// Make functions available globally for onclick handlers
window.toggleSidebar = toggleSidebar;
window.switchView = switchView;
window.openInsightDetail = openInsightDetail;
window.openClientDetail = openClientDetail;
window.closePanel = closePanel;
window.openCommandPalette = openCommandPalette;
window.closeCommandPalette = closeCommandPalette;
window.refreshData = refreshData;
window.refreshDashboard = refreshDashboard;
window.filterByCategory = filterByCategory;

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
