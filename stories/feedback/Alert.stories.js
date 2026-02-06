/**
 * Alert Component Stories
 *
 * Demonstrates inline alerts and banners.
 */

export default {
  title: 'Components/Feedback/Alert',
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'select',
      options: ['success', 'error', 'warning', 'info'],
      description: 'Alert variant'
    },
    dismissible: {
      control: 'boolean',
      description: 'Show close button'
    }
  }
};

// Icon definitions
const icons = {
  success: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/></svg>',
  error: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="m15 9-6 6M9 9l6 6"/></svg>',
  warning: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3M12 9v4M12 17h.01"/></svg>',
  info: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>'
};

// Helper to create alert HTML
const createAlert = ({ variant = 'info', title = '', message, dismissible = false }) => `
  <div class="alert alert-${variant}" role="alert" style="max-width: 500px;">
    <span class="alert-icon">${icons[variant]}</span>
    <div class="alert-content">
      ${title ? `<p class="alert-title">${title}</p>` : ''}
      <p class="alert-message">${message}</p>
    </div>
    ${dismissible ? `
      <button type="button" class="alert-close" onclick="this.parentElement.remove()" aria-label="Close">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M18 6 6 18M6 6l12 12"/>
        </svg>
      </button>
    ` : ''}
  </div>
`;

// Success Alert
export const Success = {
  args: {
    variant: 'success',
    title: 'Success!',
    message: 'Your tax return has been submitted successfully.'
  },
  render: (args) => createAlert(args)
};

// Error Alert
export const Error = {
  args: {
    variant: 'error',
    title: 'Error',
    message: 'There was a problem processing your request. Please try again.'
  },
  render: (args) => createAlert(args)
};

// Warning Alert
export const Warning = {
  args: {
    variant: 'warning',
    title: 'Warning',
    message: 'Your session will expire in 5 minutes. Please save your work.'
  },
  render: (args) => createAlert(args)
};

// Info Alert
export const Info = {
  args: {
    variant: 'info',
    title: 'Information',
    message: 'Tax filing deadline for 2024 is April 15, 2025.'
  },
  render: (args) => createAlert(args)
};

// Without Title
export const WithoutTitle = {
  args: {
    variant: 'info',
    message: 'This is a simple alert without a title.'
  },
  render: (args) => createAlert(args)
};

// Dismissible
export const Dismissible = {
  args: {
    variant: 'success',
    title: 'Saved',
    message: 'Your changes have been saved. Click X to dismiss this alert.',
    dismissible: true
  },
  render: (args) => createAlert(args)
};

// All Variants
export const AllVariants = {
  render: () => `
    <div style="display: flex; flex-direction: column; gap: 16px; max-width: 500px;">
      ${createAlert({ variant: 'success', title: 'Success', message: 'Your changes have been saved.' })}
      ${createAlert({ variant: 'error', title: 'Error', message: 'Something went wrong. Please try again.' })}
      ${createAlert({ variant: 'warning', title: 'Warning', message: 'Please review your information before submitting.' })}
      ${createAlert({ variant: 'info', title: 'Info', message: 'Tax documents are due by April 15th.' })}
    </div>
  `
};

// Banner Component
export const Banners = {
  render: () => `
    <div style="display: flex; flex-direction: column; gap: 8px;">
      <div class="banner banner-info" role="alert">
        <div class="banner-content">
          <span>New feature: E-file is now available for all tax years!</span>
          <a href="#" style="font-weight: 500; text-decoration: underline;">Learn more</a>
        </div>
        <button type="button" class="banner-close" onclick="this.parentElement.remove()" aria-label="Close">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 6 6 18M6 6l12 12"/>
          </svg>
        </button>
      </div>

      <div class="banner banner-warning" role="alert">
        <div class="banner-content">
          <span>Scheduled maintenance on Sunday, March 15th from 2-4 AM EST</span>
        </div>
      </div>

      <div class="banner banner-error" role="alert">
        <div class="banner-content">
          <span>Service disruption: Some features may be unavailable</span>
          <a href="#" style="font-weight: 500; text-decoration: underline;">Check status</a>
        </div>
      </div>

      <div class="banner banner-success" role="alert">
        <div class="banner-content">
          <span>All systems operational</span>
        </div>
      </div>
    </div>
  `
};

// Long Content
export const LongContent = {
  render: () => createAlert({
    variant: 'info',
    title: 'Important Information',
    message: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.'
  })
};
