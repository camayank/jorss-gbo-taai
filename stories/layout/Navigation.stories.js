/**
 * Navigation Component Stories
 *
 * Demonstrates breadcrumbs, tabs, and navigation patterns.
 */

export default {
  title: 'Components/Layout/Navigation',
  tags: ['autodocs']
};

// Breadcrumbs
export const Breadcrumbs = {
  render: () => `
    <div style="display: flex; flex-direction: column; gap: 24px;">
      <nav class="breadcrumbs" aria-label="Breadcrumb">
        <div class="breadcrumb-item">
          <a href="#">Home</a>
        </div>
        <span class="breadcrumb-separator" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 18 6-6-6-6"/></svg>
        </span>
        <div class="breadcrumb-item">
          <a href="#">Clients</a>
        </div>
        <span class="breadcrumb-separator" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 18 6-6-6-6"/></svg>
        </span>
        <div class="breadcrumb-item current">
          <span>John Doe</span>
        </div>
      </nav>

      <nav class="breadcrumbs" aria-label="Breadcrumb">
        <div class="breadcrumb-item">
          <a href="#">Dashboard</a>
        </div>
        <span class="breadcrumb-separator" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 18 6-6-6-6"/></svg>
        </span>
        <div class="breadcrumb-item">
          <a href="#">Tax Returns</a>
        </div>
        <span class="breadcrumb-separator" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 18 6-6-6-6"/></svg>
        </span>
        <div class="breadcrumb-item">
          <a href="#">2024</a>
        </div>
        <span class="breadcrumb-separator" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 18 6-6-6-6"/></svg>
        </span>
        <div class="breadcrumb-item current">
          <span>Edit</span>
        </div>
      </nav>
    </div>
  `
};

// Tabs
export const Tabs = {
  render: () => `
    <div style="display: flex; flex-direction: column; gap: 32px;">
      <!-- Default Tabs -->
      <div>
        <p style="margin: 0 0 12px; font-size: 14px; color: #6b7280;">Default Tabs</p>
        <nav class="tabs" role="tablist">
          <a href="#" class="tab active" role="tab" aria-selected="true">Overview</a>
          <a href="#" class="tab" role="tab" aria-selected="false">Documents</a>
          <a href="#" class="tab" role="tab" aria-selected="false">Tax Returns</a>
          <a href="#" class="tab" role="tab" aria-selected="false">Settings</a>
        </nav>
      </div>

      <!-- Pills Style Tabs -->
      <div>
        <p style="margin: 0 0 12px; font-size: 14px; color: #6b7280;">Pills Style</p>
        <nav class="tabs tabs-pills" role="tablist" style="display: inline-flex;">
          <a href="#" class="tab active" role="tab" aria-selected="true">Day</a>
          <a href="#" class="tab" role="tab" aria-selected="false">Week</a>
          <a href="#" class="tab" role="tab" aria-selected="false">Month</a>
          <a href="#" class="tab" role="tab" aria-selected="false">Year</a>
        </nav>
      </div>

      <!-- Tabs with Badges -->
      <div>
        <p style="margin: 0 0 12px; font-size: 14px; color: #6b7280;">With Badges</p>
        <nav class="tabs" role="tablist">
          <a href="#" class="tab active" role="tab" aria-selected="true">
            All Clients
            <span style="margin-left: 8px; background: var(--color-gray-200); padding: 2px 8px; border-radius: 9999px; font-size: 12px;">128</span>
          </a>
          <a href="#" class="tab" role="tab" aria-selected="false">
            Pending
            <span style="margin-left: 8px; background: var(--color-warning-100); color: var(--color-warning-700); padding: 2px 8px; border-radius: 9999px; font-size: 12px;">12</span>
          </a>
          <a href="#" class="tab" role="tab" aria-selected="false">
            Completed
            <span style="margin-left: 8px; background: var(--color-success-100); color: var(--color-success-700); padding: 2px 8px; border-radius: 9999px; font-size: 12px;">89</span>
          </a>
        </nav>
      </div>
    </div>
  `
};

// Steps/Progress
export const Steps = {
  render: () => `
    <div style="display: flex; flex-direction: column; gap: 48px;">
      <!-- Step 1 Active -->
      <div>
        <p style="margin: 0 0 16px; font-size: 14px; color: #6b7280;">Step 1 of 4</p>
        <nav style="display: flex; align-items: center;" aria-label="Progress">
          <div style="display: flex; align-items: center;">
            <div style="width: 32px; height: 32px; border-radius: 50%; background: var(--color-primary-500); color: white; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 500;">1</div>
            <span style="margin-left: 12px; font-size: 14px; font-weight: 600; color: var(--color-gray-900);">Personal Info</span>
          </div>
          <div style="flex: 1; height: 2px; margin: 0 16px; background: var(--color-gray-200);"></div>
          <div style="display: flex; align-items: center;">
            <div style="width: 32px; height: 32px; border-radius: 50%; background: var(--color-gray-200); color: var(--color-gray-500); display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 500;">2</div>
            <span style="margin-left: 12px; font-size: 14px; color: var(--color-gray-500);">Documents</span>
          </div>
          <div style="flex: 1; height: 2px; margin: 0 16px; background: var(--color-gray-200);"></div>
          <div style="display: flex; align-items: center;">
            <div style="width: 32px; height: 32px; border-radius: 50%; background: var(--color-gray-200); color: var(--color-gray-500); display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 500;">3</div>
            <span style="margin-left: 12px; font-size: 14px; color: var(--color-gray-500);">Review</span>
          </div>
          <div style="flex: 1; height: 2px; margin: 0 16px; background: var(--color-gray-200);"></div>
          <div style="display: flex; align-items: center;">
            <div style="width: 32px; height: 32px; border-radius: 50%; background: var(--color-gray-200); color: var(--color-gray-500); display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 500;">4</div>
            <span style="margin-left: 12px; font-size: 14px; color: var(--color-gray-500);">Submit</span>
          </div>
        </nav>
      </div>

      <!-- Step 3 Active (with completed steps) -->
      <div>
        <p style="margin: 0 0 16px; font-size: 14px; color: #6b7280;">Step 3 of 4</p>
        <nav style="display: flex; align-items: center;" aria-label="Progress">
          <div style="display: flex; align-items: center;">
            <div style="width: 32px; height: 32px; border-radius: 50%; background: var(--color-success-500); color: white; display: flex; align-items: center; justify-content: center;">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M20 6 9 17l-5-5"/></svg>
            </div>
            <span style="margin-left: 12px; font-size: 14px; color: var(--color-gray-500);">Personal Info</span>
          </div>
          <div style="flex: 1; height: 2px; margin: 0 16px; background: var(--color-success-500);"></div>
          <div style="display: flex; align-items: center;">
            <div style="width: 32px; height: 32px; border-radius: 50%; background: var(--color-success-500); color: white; display: flex; align-items: center; justify-content: center;">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="M20 6 9 17l-5-5"/></svg>
            </div>
            <span style="margin-left: 12px; font-size: 14px; color: var(--color-gray-500);">Documents</span>
          </div>
          <div style="flex: 1; height: 2px; margin: 0 16px; background: var(--color-success-500);"></div>
          <div style="display: flex; align-items: center;">
            <div style="width: 32px; height: 32px; border-radius: 50%; background: var(--color-primary-500); color: white; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 500;">3</div>
            <span style="margin-left: 12px; font-size: 14px; font-weight: 600; color: var(--color-gray-900);">Review</span>
          </div>
          <div style="flex: 1; height: 2px; margin: 0 16px; background: var(--color-gray-200);"></div>
          <div style="display: flex; align-items: center;">
            <div style="width: 32px; height: 32px; border-radius: 50%; background: var(--color-gray-200); color: var(--color-gray-500); display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 500;">4</div>
            <span style="margin-left: 12px; font-size: 14px; color: var(--color-gray-500);">Submit</span>
          </div>
        </nav>
      </div>
    </div>
  `
};

// Page Header
export const PageHeader = {
  render: () => `
    <div style="display: flex; flex-direction: column; gap: 32px;">
      <!-- Simple Page Header -->
      <div style="background: white; padding: 24px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 16px;">
          <div>
            <h1 style="font-size: 24px; font-weight: 600; color: var(--color-gray-900); margin: 0;">Clients</h1>
            <p style="font-size: 14px; color: var(--color-gray-500); margin: 4px 0 0;">Manage your client list and tax returns</p>
          </div>
          <button class="btn btn-primary">Add Client</button>
        </div>
      </div>

      <!-- Page Header with Breadcrumb -->
      <div style="background: white; padding: 24px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
        <nav class="breadcrumbs" style="margin-bottom: 12px;">
          <div class="breadcrumb-item"><a href="#">Clients</a></div>
          <span class="breadcrumb-separator"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 18 6-6-6-6"/></svg></span>
          <div class="breadcrumb-item current"><span>John Doe</span></div>
        </nav>
        <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap;">
          <div>
            <h1 style="font-size: 24px; font-weight: 600; color: var(--color-gray-900); margin: 0;">John Doe</h1>
            <p style="font-size: 14px; color: var(--color-gray-500); margin: 4px 0 0;">Client since January 2024</p>
          </div>
          <div style="display: flex; gap: 12px;">
            <button class="btn btn-ghost">Edit</button>
            <button class="btn btn-primary">Start Return</button>
          </div>
        </div>
      </div>
    </div>
  `
};

// Sidebar Navigation (Static Preview)
export const SidebarNavigation = {
  render: () => `
    <div style="display: flex; gap: 24px;">
      <!-- Full Sidebar -->
      <div style="width: 260px; background: var(--color-primary-900); border-radius: 8px; overflow: hidden;">
        <div style="height: 64px; padding: 0 16px; display: flex; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.1);">
          <span style="font-size: 18px; font-weight: 600; color: white;">TaxPlatform</span>
        </div>
        <div style="padding: 16px 0;">
          <div style="padding: 0 20px; margin-bottom: 8px; font-size: 11px; font-weight: 600; color: rgba(255,255,255,0.4); text-transform: uppercase; letter-spacing: 0.05em;">Main</div>
          <ul style="list-style: none; padding: 0; margin: 0;">
            <li>
              <a href="#" class="nav-item active" style="margin: 2px 12px;">
                <span class="nav-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg></span>
                <span class="nav-label">Dashboard</span>
              </a>
            </li>
            <li>
              <a href="#" class="nav-item" style="margin: 2px 12px;">
                <span class="nav-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg></span>
                <span class="nav-label">Clients</span>
                <span class="nav-badge">12</span>
              </a>
            </li>
            <li>
              <a href="#" class="nav-item" style="margin: 2px 12px;">
                <span class="nav-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/></svg></span>
                <span class="nav-label">Documents</span>
              </a>
            </li>
          </ul>
          <div style="padding: 0 20px; margin: 24px 0 8px; font-size: 11px; font-weight: 600; color: rgba(255,255,255,0.4); text-transform: uppercase; letter-spacing: 0.05em;">Tax</div>
          <ul style="list-style: none; padding: 0; margin: 0;">
            <li>
              <a href="#" class="nav-item" style="margin: 2px 12px;">
                <span class="nav-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg></span>
                <span class="nav-label">Tax Returns</span>
              </a>
            </li>
            <li>
              <a href="#" class="nav-item" style="margin: 2px 12px;">
                <span class="nav-icon"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20V10M18 20V4M6 20v-4"/></svg></span>
                <span class="nav-label">Reports</span>
              </a>
            </li>
          </ul>
        </div>
      </div>

      <!-- Collapsed Sidebar -->
      <div style="width: 72px; background: var(--color-primary-900); border-radius: 8px; overflow: hidden;">
        <div style="height: 64px; display: flex; align-items: center; justify-content: center; border-bottom: 1px solid rgba(255,255,255,0.1);">
          <span style="font-size: 20px; font-weight: 700; color: white;">T</span>
        </div>
        <div style="padding: 16px 0;">
          <ul style="list-style: none; padding: 0; margin: 0;">
            <li>
              <a href="#" style="display: flex; align-items: center; justify-content: center; padding: 12px; margin: 4px 8px; border-radius: 8px; background: var(--color-accent-500); color: white;">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
              </a>
            </li>
            <li>
              <a href="#" style="display: flex; align-items: center; justify-content: center; padding: 12px; margin: 4px 8px; border-radius: 8px; color: rgba(255,255,255,0.6);">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg>
              </a>
            </li>
            <li>
              <a href="#" style="display: flex; align-items: center; justify-content: center; padding: 12px; margin: 4px 8px; border-radius: 8px; color: rgba(255,255,255,0.6);">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/></svg>
              </a>
            </li>
          </ul>
        </div>
      </div>
    </div>
  `
};
