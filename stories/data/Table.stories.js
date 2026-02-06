/**
 * Table Component Stories
 *
 * Demonstrates data tables with sorting, selection, and pagination.
 */

export default {
  title: 'Components/Data/Table',
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'select',
      options: ['default', 'striped', 'bordered'],
      description: 'Table variant'
    },
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
      description: 'Table size'
    }
  }
};

// Sample data
const clients = [
  { name: 'John Doe', email: 'john@example.com', status: 'Active', returns: 3 },
  { name: 'Jane Smith', email: 'jane@example.com', status: 'Pending', returns: 1 },
  { name: 'Bob Johnson', email: 'bob@example.com', status: 'Active', returns: 5 },
  { name: 'Alice Brown', email: 'alice@example.com', status: 'Inactive', returns: 2 },
  { name: 'Charlie Wilson', email: 'charlie@example.com', status: 'Active', returns: 4 }
];

// Basic Table
export const BasicTable = {
  render: () => `
    <div class="table-container">
      <table class="table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Status</th>
            <th class="text-right">Returns</th>
          </tr>
        </thead>
        <tbody>
          ${clients.map(c => `
            <tr>
              <td>${c.name}</td>
              <td>${c.email}</td>
              <td>${c.status}</td>
              <td class="text-right">${c.returns}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `
};

// Striped Table
export const StripedTable = {
  render: () => `
    <div class="table-container">
      <table class="table table-striped">
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Status</th>
            <th class="text-right">Returns</th>
          </tr>
        </thead>
        <tbody>
          ${clients.map(c => `
            <tr>
              <td>${c.name}</td>
              <td>${c.email}</td>
              <td>${c.status}</td>
              <td class="text-right">${c.returns}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `
};

// Hoverable Table
export const HoverableTable = {
  render: () => `
    <div class="table-container">
      <table class="table table-hover">
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Status</th>
            <th class="text-right">Returns</th>
          </tr>
        </thead>
        <tbody>
          ${clients.map(c => `
            <tr>
              <td>${c.name}</td>
              <td>${c.email}</td>
              <td>${c.status}</td>
              <td class="text-right">${c.returns}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `
};

// With Status Cells
export const WithStatusCells = {
  render: () => `
    <div class="table-container">
      <table class="table table-hover">
        <thead>
          <tr>
            <th>Client</th>
            <th>Email</th>
            <th>Status</th>
            <th class="text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>
              <div class="cell-with-avatar">
                <div class="table-avatar">JD</div>
                <div>
                  <div style="font-weight: 500;">John Doe</div>
                  <div style="font-size: 12px; color: #6b7280;">Tax ID: XXX-XX-1234</div>
                </div>
              </div>
            </td>
            <td>john@example.com</td>
            <td>
              <span class="cell-status">
                <span class="status-dot success"></span>
                <span>Filed</span>
              </span>
            </td>
            <td class="row-actions">
              <div class="row-actions-menu">
                <button class="row-action-btn" title="View">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                </button>
                <button class="row-action-btn" title="Edit">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                </button>
                <button class="row-action-btn danger" title="Delete">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                </button>
              </div>
            </td>
          </tr>
          <tr>
            <td>
              <div class="cell-with-avatar">
                <div class="table-avatar">JS</div>
                <div>
                  <div style="font-weight: 500;">Jane Smith</div>
                  <div style="font-size: 12px; color: #6b7280;">Tax ID: XXX-XX-5678</div>
                </div>
              </div>
            </td>
            <td>jane@example.com</td>
            <td>
              <span class="cell-status">
                <span class="status-dot warning"></span>
                <span>Pending Review</span>
              </span>
            </td>
            <td class="row-actions">
              <div class="row-actions-menu">
                <button class="row-action-btn" title="View">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                </button>
                <button class="row-action-btn" title="Edit">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                </button>
                <button class="row-action-btn danger" title="Delete">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                </button>
              </div>
            </td>
          </tr>
          <tr>
            <td>
              <div class="cell-with-avatar">
                <div class="table-avatar">BJ</div>
                <div>
                  <div style="font-weight: 500;">Bob Johnson</div>
                  <div style="font-size: 12px; color: #6b7280;">Tax ID: XXX-XX-9012</div>
                </div>
              </div>
            </td>
            <td>bob@example.com</td>
            <td>
              <span class="cell-status">
                <span class="status-dot error"></span>
                <span>Rejected</span>
              </span>
            </td>
            <td class="row-actions">
              <div class="row-actions-menu">
                <button class="row-action-btn" title="View">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                </button>
                <button class="row-action-btn" title="Edit">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                </button>
                <button class="row-action-btn danger" title="Delete">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  `
};

// Selectable Table
export const SelectableTable = {
  render: () => `
    <div class="table-container">
      <table class="table table-hover table-selectable">
        <thead>
          <tr>
            <th class="row-checkbox">
              <input type="checkbox" class="form-check-input">
            </th>
            <th>Name</th>
            <th>Email</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          ${clients.map((c, i) => `
            <tr class="${i === 1 ? 'selected' : ''}">
              <td class="row-checkbox">
                <input type="checkbox" class="form-check-input" ${i === 1 ? 'checked' : ''}>
              </td>
              <td>${c.name}</td>
              <td>${c.email}</td>
              <td>${c.status}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `
};

// Sortable Table
export const SortableTable = {
  render: () => `
    <div class="table-container">
      <table class="table table-sortable table-hover">
        <thead>
          <tr>
            <th>
              <span class="th-sortable th-sorted">
                Name
                <svg class="sort-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="m18 15-6-6-6 6"/>
                </svg>
              </span>
            </th>
            <th>
              <span class="th-sortable">
                Email
                <svg class="sort-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="m7 15 5 5 5-5M7 9l5-5 5 5"/>
                </svg>
              </span>
            </th>
            <th>
              <span class="th-sortable">
                Status
                <svg class="sort-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="m7 15 5 5 5-5M7 9l5-5 5 5"/>
                </svg>
              </span>
            </th>
            <th class="text-right">
              <span class="th-sortable">
                Returns
                <svg class="sort-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="m7 15 5 5 5-5M7 9l5-5 5 5"/>
                </svg>
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          ${clients.sort((a, b) => a.name.localeCompare(b.name)).map(c => `
            <tr>
              <td>${c.name}</td>
              <td>${c.email}</td>
              <td>${c.status}</td>
              <td class="text-right">${c.returns}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `
};

// With Pagination
export const WithPagination = {
  render: () => `
    <div class="table-container">
      <table class="table table-hover">
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Status</th>
            <th class="text-right">Returns</th>
          </tr>
        </thead>
        <tbody>
          ${clients.map(c => `
            <tr>
              <td>${c.name}</td>
              <td>${c.email}</td>
              <td>${c.status}</td>
              <td class="text-right">${c.returns}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      <div class="table-pagination">
        <span class="pagination-info">Showing 1 to 5 of 128 results</span>
        <div class="pagination-controls">
          <button class="pagination-btn" disabled>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m15 18-6-6 6-6"/></svg>
          </button>
          <button class="pagination-btn active">1</button>
          <button class="pagination-btn">2</button>
          <button class="pagination-btn">3</button>
          <span style="padding: 0 4px; color: #9ca3af;">...</span>
          <button class="pagination-btn">26</button>
          <button class="pagination-btn">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 18 6-6-6-6"/></svg>
          </button>
        </div>
      </div>
    </div>
  `
};

// Empty State
export const EmptyState = {
  render: () => `
    <div class="table-container">
      <table class="table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td colspan="3">
              <div class="table-empty">
                <div class="table-empty-icon">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                    <path d="M22 12h-6l-2 3h-4l-2-3H2"/>
                    <path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>
                  </svg>
                </div>
                <p class="table-empty-title">No clients found</p>
                <p class="table-empty-message">Get started by adding your first client.</p>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  `
};

// Compact Table
export const CompactTable = {
  render: () => `
    <div class="table-container">
      <table class="table table-sm table-striped">
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Status</th>
            <th class="text-right">Returns</th>
          </tr>
        </thead>
        <tbody>
          ${clients.map(c => `
            <tr>
              <td>${c.name}</td>
              <td>${c.email}</td>
              <td>${c.status}</td>
              <td class="text-right">${c.returns}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `
};

// All Status Types
export const StatusTypes = {
  render: () => `
    <div style="display: flex; flex-wrap: wrap; gap: 24px;">
      <span class="cell-status"><span class="status-dot success"></span><span>Success / Active / Filed</span></span>
      <span class="cell-status"><span class="status-dot warning"></span><span>Warning / Pending</span></span>
      <span class="cell-status"><span class="status-dot error"></span><span>Error / Rejected</span></span>
      <span class="cell-status"><span class="status-dot info"></span><span>Info / Draft</span></span>
      <span class="cell-status"><span class="status-dot neutral"></span><span>Neutral / Inactive</span></span>
    </div>
  `
};
