/**
 * Card Component Stories
 *
 * Demonstrates card variants, layouts, and specialized cards.
 */

export default {
  title: 'Components/Layout/Card',
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'select',
      options: ['default', 'flat', 'elevated', 'bordered', 'interactive'],
      description: 'Card variant'
    },
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
      description: 'Card size'
    }
  }
};

// Basic Card
export const BasicCard = {
  render: () => `
    <div class="card" style="max-width: 400px;">
      <div class="card-header">
        <h3 class="card-title">Card Title</h3>
      </div>
      <div class="card-body">
        <p>This is a basic card with a header and body content. Cards are versatile containers for displaying grouped information.</p>
      </div>
    </div>
  `
};

// With Subtitle
export const WithSubtitle = {
  render: () => `
    <div class="card" style="max-width: 400px;">
      <div class="card-header">
        <div>
          <h3 class="card-title">Client Information</h3>
          <p class="card-subtitle">Last updated: February 6, 2026</p>
        </div>
      </div>
      <div class="card-body">
        <p>Card content with header subtitle for additional context.</p>
      </div>
    </div>
  `
};

// With Header Actions
export const WithHeaderActions = {
  render: () => `
    <div class="card" style="max-width: 500px;">
      <div class="card-header">
        <h3 class="card-title">Recent Documents</h3>
        <button class="btn btn-primary btn-sm">Upload</button>
      </div>
      <div class="card-body">
        <p>Cards can have action buttons in the header for common operations.</p>
      </div>
    </div>
  `
};

// With Footer
export const WithFooter = {
  render: () => `
    <div class="card" style="max-width: 400px;">
      <div class="card-header">
        <h3 class="card-title">Edit Profile</h3>
      </div>
      <div class="card-body">
        <div class="form-group">
          <label class="form-label">Name</label>
          <input type="text" class="form-input" value="John Doe">
        </div>
        <div class="form-group">
          <label class="form-label">Email</label>
          <input type="email" class="form-input" value="john@example.com">
        </div>
      </div>
      <div class="card-footer">
        <button class="btn btn-ghost">Cancel</button>
        <button class="btn btn-primary">Save Changes</button>
      </div>
    </div>
  `
};

// Card Variants
export const CardVariants = {
  render: () => `
    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 24px; max-width: 800px;">
      <div class="card">
        <div class="card-body">
          <h4 style="margin: 0 0 8px; font-weight: 600;">Default Card</h4>
          <p style="margin: 0; color: #6b7280; font-size: 14px;">Standard card with border and shadow</p>
        </div>
      </div>
      <div class="card card-flat">
        <div class="card-body">
          <h4 style="margin: 0 0 8px; font-weight: 600;">Flat Card</h4>
          <p style="margin: 0; color: #6b7280; font-size: 14px;">No shadow, just border</p>
        </div>
      </div>
      <div class="card card-elevated">
        <div class="card-body">
          <h4 style="margin: 0 0 8px; font-weight: 600;">Elevated Card</h4>
          <p style="margin: 0; color: #6b7280; font-size: 14px;">Larger shadow, no border</p>
        </div>
      </div>
      <div class="card card-interactive">
        <div class="card-body">
          <h4 style="margin: 0 0 8px; font-weight: 600;">Interactive Card</h4>
          <p style="margin: 0; color: #6b7280; font-size: 14px;">Hover me! Clickable card style</p>
        </div>
      </div>
    </div>
  `
};

// Status Cards
export const StatusCards = {
  render: () => `
    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; max-width: 600px;">
      <div class="card card-success">
        <div class="card-body">
          <h4 style="margin: 0 0 8px; font-weight: 600;">Success</h4>
          <p style="margin: 0; color: #6b7280; font-size: 14px;">Tax return filed successfully</p>
        </div>
      </div>
      <div class="card card-warning">
        <div class="card-body">
          <h4 style="margin: 0 0 8px; font-weight: 600;">Warning</h4>
          <p style="margin: 0; color: #6b7280; font-size: 14px;">Documents pending review</p>
        </div>
      </div>
      <div class="card card-error">
        <div class="card-body">
          <h4 style="margin: 0 0 8px; font-weight: 600;">Error</h4>
          <p style="margin: 0; color: #6b7280; font-size: 14px;">Validation errors found</p>
        </div>
      </div>
      <div class="card card-info">
        <div class="card-body">
          <h4 style="margin: 0 0 8px; font-weight: 600;">Info</h4>
          <p style="margin: 0; color: #6b7280; font-size: 14px;">Additional information available</p>
        </div>
      </div>
    </div>
  `
};

// Stat Cards
export const StatCards = {
  render: () => `
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;">
      <div class="card stat-card">
        <p class="stat-card-label">Total Clients</p>
        <p class="stat-card-value">1,234</p>
        <div class="stat-card-change positive">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m18 15-6-6-6 6"/></svg>
          <span>12% from last month</span>
        </div>
      </div>
      <div class="card stat-card">
        <p class="stat-card-label">Returns Filed</p>
        <p class="stat-card-value">856</p>
        <div class="stat-card-change positive">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m18 15-6-6-6 6"/></svg>
          <span>8% from last month</span>
        </div>
      </div>
      <div class="card stat-card">
        <p class="stat-card-label">Revenue</p>
        <p class="stat-card-value">$45,231</p>
        <div class="stat-card-change negative">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m6 9 6 6 6-6"/></svg>
          <span>3% from last month</span>
        </div>
      </div>
      <div class="card stat-card">
        <p class="stat-card-label">Pending</p>
        <p class="stat-card-value">23</p>
      </div>
    </div>
  `
};

// Feature Cards
export const FeatureCards = {
  render: () => `
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px;">
      <div class="card feature-card">
        <div class="feature-card-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/></svg>
        </div>
        <h4 class="feature-card-title">Document Upload</h4>
        <p class="feature-card-description">Securely upload your tax documents and we'll handle the rest.</p>
      </div>
      <div class="card feature-card">
        <div class="feature-card-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
        </div>
        <h4 class="feature-card-title">Secure Storage</h4>
        <p class="feature-card-description">Bank-level encryption keeps your sensitive data protected.</p>
      </div>
      <div class="card feature-card">
        <div class="feature-card-icon">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/></svg>
        </div>
        <h4 class="feature-card-title">Fast Filing</h4>
        <p class="feature-card-description">E-file your returns and get your refund faster than ever.</p>
      </div>
    </div>
  `
};

// Profile Card
export const ProfileCard = {
  render: () => `
    <div class="card profile-card" style="max-width: 300px;">
      <div class="profile-card-avatar">JD</div>
      <h4 class="profile-card-name">John Doe</h4>
      <p class="profile-card-role">Senior Tax Consultant</p>
      <div style="margin-top: 16px; display: flex; gap: 8px; justify-content: center;">
        <button class="btn btn-outline btn-sm">Message</button>
        <button class="btn btn-primary btn-sm">View Profile</button>
      </div>
    </div>
  `
};

// List Card
export const ListCard = {
  render: () => `
    <div class="card" style="max-width: 400px;">
      <div class="card-header">
        <h3 class="card-title">Recent Activity</h3>
      </div>
      <div class="card-list">
        <div class="card-list-item card-list-item-interactive">
          <div style="width: 40px; height: 40px; border-radius: 50%; background: #dbeafe; display: flex; align-items: center; justify-content: center;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/></svg>
          </div>
          <div style="flex: 1;">
            <p style="margin: 0; font-weight: 500;">W-2 Uploaded</p>
            <p style="margin: 2px 0 0; font-size: 13px; color: #6b7280;">2 minutes ago</p>
          </div>
        </div>
        <div class="card-list-item card-list-item-interactive">
          <div style="width: 40px; height: 40px; border-radius: 50%; background: #dcfce7; display: flex; align-items: center; justify-content: center;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/></svg>
          </div>
          <div style="flex: 1;">
            <p style="margin: 0; font-weight: 500;">Return Submitted</p>
            <p style="margin: 2px 0 0; font-size: 13px; color: #6b7280;">1 hour ago</p>
          </div>
        </div>
        <div class="card-list-item card-list-item-interactive">
          <div style="width: 40px; height: 40px; border-radius: 50%; background: #fef3c7; display: flex; align-items: center; justify-content: center;">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#d97706" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
          </div>
          <div style="flex: 1;">
            <p style="margin: 0; font-weight: 500;">Review Required</p>
            <p style="margin: 2px 0 0; font-size: 13px; color: #6b7280;">Yesterday</p>
          </div>
        </div>
      </div>
    </div>
  `
};

// Card Grid
export const CardGrid = {
  render: () => `
    <div class="card-grid" style="max-width: 900px;">
      ${[1, 2, 3, 4, 5, 6].map(i => `
        <div class="card card-interactive">
          <div class="card-body">
            <h4 style="margin: 0 0 8px; font-weight: 600;">Card ${i}</h4>
            <p style="margin: 0; color: #6b7280; font-size: 14px;">This is a card in a responsive grid layout.</p>
          </div>
        </div>
      `).join('')}
    </div>
  `
};
