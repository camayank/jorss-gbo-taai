/**
 * Input Component Stories
 *
 * Demonstrates text input variants, sizes, and states.
 */

export default {
  title: 'Components/Forms/Input',
  tags: ['autodocs'],
  argTypes: {
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
      description: 'Input size'
    },
    state: {
      control: 'select',
      options: ['default', 'valid', 'invalid'],
      description: 'Validation state'
    },
    disabled: {
      control: 'boolean',
      description: 'Disabled state'
    },
    required: {
      control: 'boolean',
      description: 'Required field'
    }
  }
};

// Helper to create input HTML
const createInput = ({
  name = 'input',
  label = '',
  type = 'text',
  placeholder = '',
  value = '',
  size = 'md',
  state = 'default',
  disabled = false,
  required = false,
  helper = '',
  error = '',
  addonLeft = '',
  addonRight = ''
}) => {
  const sizeClass = size !== 'md' ? `form-input-${size}` : '';
  const stateClass = state === 'valid' ? 'is-valid' : state === 'invalid' ? 'is-invalid' : '';

  let inputHtml;

  if (addonLeft || addonRight) {
    inputHtml = `
      <div class="input-group">
        ${addonLeft ? `<span class="input-addon">${addonLeft}</span>` : ''}
        <input
          type="${type}"
          id="${name}"
          name="${name}"
          class="form-input ${sizeClass} ${stateClass}"
          placeholder="${placeholder}"
          value="${value}"
          ${disabled ? 'disabled' : ''}
          ${required ? 'required' : ''}
        >
        ${addonRight ? `<span class="input-addon">${addonRight}</span>` : ''}
      </div>
    `;
  } else {
    inputHtml = `
      <input
        type="${type}"
        id="${name}"
        name="${name}"
        class="form-input ${sizeClass} ${stateClass}"
        placeholder="${placeholder}"
        value="${value}"
        ${disabled ? 'disabled' : ''}
        ${required ? 'required' : ''}
      >
    `;
  }

  return `
    <div class="form-group" style="max-width: 320px;">
      ${label ? `<label class="form-label ${required ? 'required' : ''}" for="${name}">${label}</label>` : ''}
      ${inputHtml}
      ${error ? `<p class="form-error"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg> ${error}</p>` : ''}
      ${helper && !error ? `<p class="form-helper">${helper}</p>` : ''}
    </div>
  `;
};

// Default Input
export const Default = {
  args: {
    label: 'Email Address',
    name: 'email',
    type: 'email',
    placeholder: 'you@example.com'
  },
  render: (args) => createInput(args)
};

// With Helper Text
export const WithHelper = {
  args: {
    label: 'Password',
    name: 'password',
    type: 'password',
    placeholder: 'Enter your password',
    helper: 'Must be at least 8 characters'
  },
  render: (args) => createInput(args)
};

// Required Field
export const Required = {
  args: {
    label: 'Full Name',
    name: 'fullname',
    placeholder: 'John Doe',
    required: true
  },
  render: (args) => createInput(args)
};

// Valid State
export const ValidState = {
  args: {
    label: 'Email',
    name: 'email_valid',
    type: 'email',
    value: 'user@example.com',
    state: 'valid'
  },
  render: (args) => createInput(args)
};

// Error State
export const ErrorState = {
  args: {
    label: 'Email',
    name: 'email_error',
    type: 'email',
    value: 'invalid-email',
    state: 'invalid',
    error: 'Please enter a valid email address'
  },
  render: (args) => createInput(args)
};

// Disabled
export const Disabled = {
  args: {
    label: 'Disabled Input',
    name: 'disabled_input',
    value: 'Cannot edit this',
    disabled: true
  },
  render: (args) => createInput(args)
};

// All Sizes
export const AllSizes = {
  render: () => `
    <div style="display: flex; flex-direction: column; gap: 24px; max-width: 320px;">
      ${createInput({ label: 'Small Input', name: 'small', placeholder: 'Small size', size: 'sm' })}
      ${createInput({ label: 'Medium Input (Default)', name: 'medium', placeholder: 'Medium size', size: 'md' })}
      ${createInput({ label: 'Large Input', name: 'large', placeholder: 'Large size', size: 'lg' })}
    </div>
  `
};

// With Addons
export const WithAddons = {
  render: () => `
    <div style="display: flex; flex-direction: column; gap: 24px; max-width: 320px;">
      ${createInput({ label: 'Price', name: 'price', placeholder: '0.00', addonLeft: '$' })}
      ${createInput({ label: 'Website', name: 'website', placeholder: 'yoursite', addonLeft: 'https://', addonRight: '.com' })}
      ${createInput({ label: 'Amount', name: 'amount', placeholder: '100', addonRight: 'USD' })}
    </div>
  `
};

// Search Input
export const SearchInput = {
  render: () => `
    <div class="search-input" style="max-width: 320px;">
      <span class="search-icon">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
        </svg>
      </span>
      <input type="search" class="form-input" placeholder="Search...">
    </div>
  `
};

// Input Types
export const InputTypes = {
  render: () => `
    <div style="display: flex; flex-direction: column; gap: 24px; max-width: 320px;">
      ${createInput({ label: 'Text', name: 'text', type: 'text', placeholder: 'Enter text' })}
      ${createInput({ label: 'Email', name: 'email', type: 'email', placeholder: 'you@example.com' })}
      ${createInput({ label: 'Password', name: 'password', type: 'password', placeholder: 'Your password' })}
      ${createInput({ label: 'Number', name: 'number', type: 'number', placeholder: '0' })}
      ${createInput({ label: 'Date', name: 'date', type: 'date' })}
      ${createInput({ label: 'Phone', name: 'phone', type: 'tel', placeholder: '(555) 555-5555' })}
    </div>
  `
};
