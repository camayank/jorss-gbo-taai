/**
 * Toast Component Stories
 *
 * Demonstrates floating notification toasts.
 */

export default {
  title: 'Components/Feedback/Toast',
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'select',
      options: ['success', 'error', 'warning', 'info'],
      description: 'Toast variant'
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

// Helper to create toast HTML
const createToast = ({
  variant = 'info',
  title = '',
  message,
  actionText = '',
  actionHref = '#',
  showProgress = false,
  duration = 5000
}) => `
  <div class="toast toast-${variant} visible" role="alert" style="position: relative;">
    <span class="toast-icon">${icons[variant]}</span>
    <div class="toast-content">
      ${title ? `<p class="toast-title">${title}</p>` : ''}
      <p class="toast-message">${message}</p>
      ${actionText ? `
        <div class="toast-action">
          <a href="${actionHref}" class="toast-action-btn">${actionText}</a>
        </div>
      ` : ''}
    </div>
    <button type="button" class="toast-close" onclick="this.parentElement.remove()" aria-label="Close">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M18 6 6 18M6 6l12 12"/>
      </svg>
    </button>
    ${showProgress ? `<div class="toast-progress" style="animation-duration: ${duration}ms;"></div>` : ''}
  </div>
`;

// Success Toast
export const Success = {
  args: {
    variant: 'success',
    title: 'Saved!',
    message: 'Your changes have been saved successfully.'
  },
  render: (args) => createToast(args)
};

// Error Toast
export const Error = {
  args: {
    variant: 'error',
    title: 'Error',
    message: 'Failed to save changes. Please try again.'
  },
  render: (args) => createToast(args)
};

// Warning Toast
export const Warning = {
  args: {
    variant: 'warning',
    title: 'Warning',
    message: 'Your session is about to expire.'
  },
  render: (args) => createToast(args)
};

// Info Toast
export const Info = {
  args: {
    variant: 'info',
    title: 'Update Available',
    message: 'A new version is available. Refresh to update.'
  },
  render: (args) => createToast(args)
};

// Without Title
export const WithoutTitle = {
  args: {
    variant: 'success',
    message: 'File uploaded successfully.'
  },
  render: (args) => createToast(args)
};

// With Action
export const WithAction = {
  args: {
    variant: 'info',
    title: 'Document Ready',
    message: 'Your tax document is ready for download.',
    actionText: 'Download now',
    actionHref: '#'
  },
  render: (args) => createToast(args)
};

// With Progress Bar
export const WithProgressBar = {
  args: {
    variant: 'success',
    title: 'Saved',
    message: 'This toast will auto-dismiss.',
    showProgress: true,
    duration: 5000
  },
  render: (args) => createToast(args)
};

// All Variants
export const AllVariants = {
  render: () => `
    <div style="display: flex; flex-direction: column; gap: 16px;">
      ${createToast({ variant: 'success', title: 'Success', message: 'Operation completed successfully.' })}
      ${createToast({ variant: 'error', title: 'Error', message: 'Something went wrong.' })}
      ${createToast({ variant: 'warning', title: 'Warning', message: 'Please review before proceeding.' })}
      ${createToast({ variant: 'info', title: 'Info', message: 'Here is some helpful information.' })}
    </div>
  `
};

// Stacked Toasts
export const StackedToasts = {
  render: () => `
    <div style="position: relative; height: 300px;">
      <div class="toast-container" style="position: absolute;">
        ${createToast({ variant: 'success', message: 'File saved' })}
        ${createToast({ variant: 'info', title: 'Notification', message: 'You have 3 new messages' })}
        ${createToast({ variant: 'warning', message: 'Low disk space' })}
      </div>
    </div>
  `
};

// Real World Examples
export const RealWorldExamples = {
  render: () => `
    <div style="display: flex; flex-direction: column; gap: 16px;">
      ${createToast({
        variant: 'success',
        title: 'Tax Return Submitted',
        message: 'Your 2024 tax return has been submitted to the IRS.',
        actionText: 'View confirmation',
        actionHref: '#'
      })}
      ${createToast({
        variant: 'error',
        title: 'Upload Failed',
        message: 'W-2 upload failed. File size exceeds 10MB limit.',
        actionText: 'Try again',
        actionHref: '#'
      })}
      ${createToast({
        variant: 'info',
        title: 'Document Signed',
        message: 'Engagement letter signed by John Doe.',
        actionText: 'View document',
        actionHref: '#'
      })}
    </div>
  `
};
