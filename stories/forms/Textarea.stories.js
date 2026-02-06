/**
 * Textarea Component Stories
 *
 * Demonstrates textarea variants and states.
 */

export default {
  title: 'Components/Forms/Textarea',
  tags: ['autodocs'],
  argTypes: {
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
      description: 'Textarea size'
    },
    state: {
      control: 'select',
      options: ['default', 'valid', 'invalid'],
      description: 'Validation state'
    },
    disabled: {
      control: 'boolean',
      description: 'Disabled state'
    }
  }
};

// Helper to create textarea HTML
const createTextarea = ({
  name = 'textarea',
  label = '',
  placeholder = '',
  value = '',
  size = 'md',
  state = 'default',
  disabled = false,
  required = false,
  readonly = false,
  rows = 4,
  helper = '',
  error = ''
}) => {
  const sizeClass = size === 'sm' ? 'form-textarea-sm' : size === 'lg' ? 'form-textarea-lg' : '';
  const stateClass = state === 'valid' ? 'is-valid' : state === 'invalid' ? 'is-invalid' : '';

  return `
    <div class="form-group" style="max-width: 400px;">
      ${label ? `<label class="form-label ${required ? 'required' : ''}" for="${name}">${label}</label>` : ''}
      <textarea
        id="${name}"
        name="${name}"
        class="form-textarea ${sizeClass} ${stateClass}"
        placeholder="${placeholder}"
        rows="${rows}"
        ${disabled ? 'disabled' : ''}
        ${required ? 'required' : ''}
        ${readonly ? 'readonly' : ''}
      >${value}</textarea>
      ${error ? `<p class="form-error"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg> ${error}</p>` : ''}
      ${helper && !error ? `<p class="form-helper">${helper}</p>` : ''}
    </div>
  `;
};

// Default Textarea
export const Default = {
  args: {
    label: 'Description',
    name: 'description',
    placeholder: 'Enter a description...'
  },
  render: (args) => createTextarea(args)
};

// With Helper Text
export const WithHelper = {
  args: {
    label: 'Bio',
    name: 'bio',
    placeholder: 'Tell us about yourself',
    helper: 'Write a few sentences about yourself. Max 500 characters.'
  },
  render: (args) => createTextarea(args)
};

// Required Field
export const Required = {
  args: {
    label: 'Additional Comments',
    name: 'comments',
    placeholder: 'Please provide any additional information...',
    required: true
  },
  render: (args) => createTextarea(args)
};

// Error State
export const ErrorState = {
  args: {
    label: 'Message',
    name: 'message_error',
    value: 'Hi',
    state: 'invalid',
    error: 'Message must be at least 20 characters'
  },
  render: (args) => createTextarea(args)
};

// Valid State
export const ValidState = {
  args: {
    label: 'Notes',
    name: 'notes_valid',
    value: 'This is a properly filled out textarea with enough content to pass validation.',
    state: 'valid'
  },
  render: (args) => createTextarea(args)
};

// Disabled
export const Disabled = {
  args: {
    label: 'Read Only Notes',
    name: 'readonly_notes',
    value: 'This content cannot be edited.',
    disabled: true
  },
  render: (args) => createTextarea(args)
};

// All Sizes
export const AllSizes = {
  render: () => `
    <div style="display: flex; flex-direction: column; gap: 24px; max-width: 400px;">
      ${createTextarea({ label: 'Small Textarea', name: 'small', placeholder: 'Small size', size: 'sm' })}
      ${createTextarea({ label: 'Medium Textarea (Default)', name: 'medium', placeholder: 'Medium size', size: 'md' })}
      ${createTextarea({ label: 'Large Textarea', name: 'large', placeholder: 'Large size', size: 'lg' })}
    </div>
  `
};

// With Character Count
export const WithCharacterCount = {
  render: () => `
    <div class="form-group" style="max-width: 400px;">
      <label class="form-label" for="bio_count">Bio</label>
      <textarea
        id="bio_count"
        name="bio_count"
        class="form-textarea"
        placeholder="Tell us about yourself..."
        maxlength="200"
        oninput="document.getElementById('char-count').textContent = this.value.length"
      ></textarea>
      <div style="display: flex; justify-content: space-between; margin-top: 4px;">
        <p class="form-helper">Write a short bio</p>
        <p class="form-helper"><span id="char-count">0</span> / 200</p>
      </div>
    </div>
  `
};

// Tax Notes Example
export const TaxNotesExample = {
  render: () => `
    <div class="form-group" style="max-width: 500px;">
      <label class="form-label required" for="tax_notes">Additional Tax Information</label>
      <textarea
        id="tax_notes"
        name="tax_notes"
        class="form-textarea form-textarea-lg"
        placeholder="Please describe any additional deductions, credits, or special circumstances that may affect your tax return..."
        required
      ></textarea>
      <p class="form-helper">Include details about home office expenses, business losses, charitable contributions, or any other relevant information for your tax preparer.</p>
    </div>
  `
};
