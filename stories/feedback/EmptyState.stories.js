/**
 * Empty State Component Stories
 *
 * Demonstrates empty state placeholders and no-results screens.
 */

export default {
  title: 'Components/Feedback/EmptyState',
  tags: ['autodocs']
};

// Icon definitions
const icons = {
  inbox: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>',
  folder: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>',
  document: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/></svg>',
  users: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
  chart: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 20V10M18 20V4M6 20v-4"/></svg>',
  calendar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>',
  creditCard: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><path d="M1 10h22"/></svg>'
};

// Helper to create empty state
const createEmptyState = ({
  icon = 'inbox',
  title,
  description = '',
  actionText = '',
  actionHref = '#',
  secondaryText = '',
  secondaryHref = '#',
  size = 'md'
}) => {
  const sizes = {
    sm: { icon: '48px', title: '16px', desc: '14px', padding: '24px' },
    md: { icon: '64px', title: '18px', desc: '16px', padding: '40px' },
    lg: { icon: '80px', title: '20px', desc: '16px', padding: '60px' }
  };
  const s = sizes[size];

  return `
    <div style="display: flex; flex-direction: column; align-items: center; text-align: center; padding: ${s.padding};">
      <div style="width: ${s.icon}; height: ${s.icon}; color: #d1d5db; margin-bottom: 16px;">
        ${icons[icon]}
      </div>
      <h3 style="font-size: ${s.title}; font-weight: 600; color: #111827; margin: 0 0 8px;">${title}</h3>
      ${description ? `<p style="font-size: ${s.desc}; color: #6b7280; max-width: 320px; margin: 0 0 20px;">${description}</p>` : ''}
      ${actionText ? `
        <div style="display: flex; gap: 12px; flex-wrap: wrap; justify-content: center;">
          <a href="${actionHref}" class="btn btn-primary">${actionText}</a>
          ${secondaryText ? `<a href="${secondaryHref}" class="btn btn-ghost">${secondaryText}</a>` : ''}
        </div>
      ` : ''}
    </div>
  `;
};

// No Messages
export const NoMessages = {
  render: () => createEmptyState({
    icon: 'inbox',
    title: 'No messages',
    description: 'You don\'t have any messages yet. Start a conversation with your tax preparer.',
    actionText: 'Send a message'
  })
};

// No Search Results
export const NoSearchResults = {
  render: () => createEmptyState({
    icon: 'search',
    title: 'No results found',
    description: 'We couldn\'t find any clients matching "John Smith". Try adjusting your search.',
    actionText: 'Clear search',
    secondaryText: 'Add new client'
  })
};

// No Documents
export const NoDocuments = {
  render: () => createEmptyState({
    icon: 'document',
    title: 'No documents',
    description: 'Upload your tax documents to get started with your return.',
    actionText: 'Upload documents'
  })
};

// No Clients
export const NoClients = {
  render: () => createEmptyState({
    icon: 'users',
    title: 'No clients yet',
    description: 'Start building your client base by adding your first client.',
    actionText: 'Add client',
    secondaryText: 'Import from CSV'
  })
};

// No Data/Reports
export const NoReports = {
  render: () => createEmptyState({
    icon: 'chart',
    title: 'No data available',
    description: 'Once you have completed tax returns, your analytics will appear here.',
    actionText: 'View demo data'
  })
};

// No Appointments
export const NoAppointments = {
  render: () => createEmptyState({
    icon: 'calendar',
    title: 'No upcoming appointments',
    description: 'You have no scheduled appointments. Book a consultation with a tax professional.',
    actionText: 'Schedule appointment'
  })
};

// No Payment Methods
export const NoPaymentMethods = {
  render: () => createEmptyState({
    icon: 'creditCard',
    title: 'No payment methods',
    description: 'Add a payment method to pay for tax preparation services.',
    actionText: 'Add payment method'
  })
};

// Empty Folder
export const EmptyFolder = {
  render: () => createEmptyState({
    icon: 'folder',
    title: 'This folder is empty',
    description: 'Drag and drop files here or click to upload.',
    actionText: 'Upload files'
  })
};

// All Sizes
export const AllSizes = {
  render: () => `
    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px;">
      <div style="border: 1px solid #e5e7eb; border-radius: 8px;">
        ${createEmptyState({
          icon: 'inbox',
          title: 'Small',
          description: 'This is a small empty state.',
          size: 'sm'
        })}
      </div>
      <div style="border: 1px solid #e5e7eb; border-radius: 8px;">
        ${createEmptyState({
          icon: 'inbox',
          title: 'Medium',
          description: 'This is a medium empty state.',
          size: 'md'
        })}
      </div>
      <div style="border: 1px solid #e5e7eb; border-radius: 8px;">
        ${createEmptyState({
          icon: 'inbox',
          title: 'Large',
          description: 'This is a large empty state.',
          size: 'lg'
        })}
      </div>
    </div>
  `
};

// No Results with Suggestions
export const NoResultsWithSuggestions = {
  render: () => `
    <div style="display: flex; flex-direction: column; align-items: center; text-align: center; padding: 40px;">
      <div style="width: 64px; height: 64px; color: #d1d5db; margin-bottom: 16px;">
        ${icons.search}
      </div>
      <h3 style="font-size: 18px; font-weight: 600; color: #111827; margin: 0 0 8px;">
        No results for "W-3 Form"
      </h3>
      <p style="font-size: 16px; color: #6b7280; margin: 0 0 16px;">
        Try adjusting your search or filter criteria
      </p>
      <div style="margin-bottom: 16px;">
        <p style="font-size: 14px; color: #374151; margin-bottom: 8px;">Suggestions:</p>
        <ul style="list-style: none; padding: 0; margin: 0; font-size: 14px; color: #6b7280;">
          <li style="margin-bottom: 4px;">Check your spelling</li>
          <li style="margin-bottom: 4px;">Try more general terms</li>
          <li style="margin-bottom: 4px;">Try different keywords</li>
        </ul>
      </div>
      <a href="#" class="btn btn-ghost">Clear filters</a>
    </div>
  `
};

// In Context - Table
export const InContextTable = {
  render: () => `
    <div style="border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden;">
      <div style="padding: 16px 20px; border-bottom: 1px solid #e5e7eb; display: flex; justify-content: space-between; align-items: center;">
        <h3 style="margin: 0; font-size: 16px; font-weight: 600;">Recent Tax Returns</h3>
        <button class="btn btn-primary btn-sm">New Return</button>
      </div>
      <table style="width: 100%; border-collapse: collapse;">
        <thead>
          <tr style="background: #f9fafb;">
            <th style="padding: 12px 20px; text-align: left; font-size: 12px; font-weight: 600; color: #6b7280; text-transform: uppercase;">Client</th>
            <th style="padding: 12px 20px; text-align: left; font-size: 12px; font-weight: 600; color: #6b7280; text-transform: uppercase;">Tax Year</th>
            <th style="padding: 12px 20px; text-align: left; font-size: 12px; font-weight: 600; color: #6b7280; text-transform: uppercase;">Status</th>
            <th style="padding: 12px 20px; text-align: right; font-size: 12px; font-weight: 600; color: #6b7280; text-transform: uppercase;">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td colspan="4">
              ${createEmptyState({
                icon: 'document',
                title: 'No tax returns yet',
                description: 'Create your first tax return to get started.',
                actionText: 'Create tax return',
                size: 'sm'
              })}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  `
};

// In Context - Card Grid
export const InContextCardGrid = {
  render: () => `
    <div>
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <h2 style="margin: 0; font-size: 20px; font-weight: 600;">Your Documents</h2>
        <button class="btn btn-primary">Upload</button>
      </div>
      <div style="border: 2px dashed #e5e7eb; border-radius: 12px;">
        ${createEmptyState({
          icon: 'folder',
          title: 'No documents uploaded',
          description: 'Upload your W-2s, 1099s, and other tax documents to begin preparing your return.',
          actionText: 'Upload documents',
          secondaryText: 'Learn more'
        })}
      </div>
    </div>
  `
};
