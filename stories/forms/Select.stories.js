/**
 * Select Component Stories
 *
 * Demonstrates select/dropdown variants and states.
 */

export default {
  title: 'Components/Forms/Select',
  tags: ['autodocs'],
  argTypes: {
    size: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
      description: 'Select size'
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

// Helper to create select HTML
const createSelect = ({
  name = 'select',
  label = '',
  options = [],
  placeholder = '',
  selected = '',
  size = 'md',
  state = 'default',
  disabled = false,
  required = false,
  helper = '',
  error = ''
}) => {
  const sizeClass = size !== 'md' ? `form-select-${size}` : '';
  const stateClass = state === 'valid' ? 'is-valid' : state === 'invalid' ? 'is-invalid' : '';

  const optionsHtml = options.map(opt => {
    if (opt.group) {
      return `
        <optgroup label="${opt.label}">
          ${opt.options.map(o => `<option value="${o.value}" ${o.value === selected ? 'selected' : ''} ${o.disabled ? 'disabled' : ''}>${o.label}</option>`).join('')}
        </optgroup>
      `;
    }
    return `<option value="${opt.value}" ${opt.value === selected ? 'selected' : ''} ${opt.disabled ? 'disabled' : ''}>${opt.label}</option>`;
  }).join('');

  return `
    <div class="form-group" style="max-width: 320px;">
      ${label ? `<label class="form-label ${required ? 'required' : ''}" for="${name}">${label}</label>` : ''}
      <select
        id="${name}"
        name="${name}"
        class="form-select ${sizeClass} ${stateClass}"
        ${disabled ? 'disabled' : ''}
        ${required ? 'required' : ''}
      >
        ${placeholder ? `<option value="" disabled ${!selected ? 'selected' : ''}>${placeholder}</option>` : ''}
        ${optionsHtml}
      </select>
      ${error ? `<p class="form-error"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg> ${error}</p>` : ''}
      ${helper && !error ? `<p class="form-helper">${helper}</p>` : ''}
    </div>
  `;
};

const countryOptions = [
  { value: 'us', label: 'United States' },
  { value: 'ca', label: 'Canada' },
  { value: 'uk', label: 'United Kingdom' },
  { value: 'au', label: 'Australia' },
  { value: 'de', label: 'Germany' }
];

// Default Select
export const Default = {
  args: {
    label: 'Country',
    name: 'country',
    placeholder: 'Select a country',
    options: countryOptions
  },
  render: (args) => createSelect(args)
};

// With Selected Value
export const WithSelectedValue = {
  args: {
    label: 'Country',
    name: 'country_selected',
    options: countryOptions,
    selected: 'ca'
  },
  render: (args) => createSelect(args)
};

// Required Field
export const Required = {
  args: {
    label: 'State',
    name: 'state',
    placeholder: 'Select your state',
    required: true,
    options: [
      { value: 'ca', label: 'California' },
      { value: 'ny', label: 'New York' },
      { value: 'tx', label: 'Texas' },
      { value: 'fl', label: 'Florida' }
    ]
  },
  render: (args) => createSelect(args)
};

// With Helper Text
export const WithHelper = {
  args: {
    label: 'Filing Status',
    name: 'filing_status',
    placeholder: 'Select status',
    helper: 'Choose the status that matches your tax return',
    options: [
      { value: 'single', label: 'Single' },
      { value: 'married_joint', label: 'Married Filing Jointly' },
      { value: 'married_separate', label: 'Married Filing Separately' },
      { value: 'head', label: 'Head of Household' }
    ]
  },
  render: (args) => createSelect(args)
};

// Error State
export const ErrorState = {
  args: {
    label: 'Tax Year',
    name: 'tax_year_error',
    placeholder: 'Select year',
    state: 'invalid',
    error: 'Please select a tax year',
    options: [
      { value: '2024', label: '2024' },
      { value: '2023', label: '2023' },
      { value: '2022', label: '2022' }
    ]
  },
  render: (args) => createSelect(args)
};

// Disabled
export const Disabled = {
  args: {
    label: 'Disabled Select',
    name: 'disabled_select',
    options: countryOptions,
    selected: 'us',
    disabled: true
  },
  render: (args) => createSelect(args)
};

// All Sizes
export const AllSizes = {
  render: () => `
    <div style="display: flex; flex-direction: column; gap: 24px; max-width: 320px;">
      ${createSelect({ label: 'Small Select', name: 'small', size: 'sm', placeholder: 'Small', options: countryOptions })}
      ${createSelect({ label: 'Medium Select (Default)', name: 'medium', size: 'md', placeholder: 'Medium', options: countryOptions })}
      ${createSelect({ label: 'Large Select', name: 'large', size: 'lg', placeholder: 'Large', options: countryOptions })}
    </div>
  `
};

// With Option Groups
export const WithOptionGroups = {
  render: () => createSelect({
    label: 'Choose a Region',
    name: 'region',
    placeholder: 'Select region',
    options: [
      {
        group: true,
        label: 'North America',
        options: [
          { value: 'us', label: 'United States' },
          { value: 'ca', label: 'Canada' },
          { value: 'mx', label: 'Mexico' }
        ]
      },
      {
        group: true,
        label: 'Europe',
        options: [
          { value: 'uk', label: 'United Kingdom' },
          { value: 'de', label: 'Germany' },
          { value: 'fr', label: 'France' }
        ]
      },
      {
        group: true,
        label: 'Asia Pacific',
        options: [
          { value: 'jp', label: 'Japan' },
          { value: 'au', label: 'Australia' },
          { value: 'sg', label: 'Singapore' }
        ]
      }
    ]
  })
};

// With Disabled Options
export const WithDisabledOptions = {
  render: () => createSelect({
    label: 'Subscription Plan',
    name: 'plan',
    placeholder: 'Select a plan',
    options: [
      { value: 'free', label: 'Free' },
      { value: 'starter', label: 'Starter - $9/mo' },
      { value: 'pro', label: 'Pro - $29/mo' },
      { value: 'enterprise', label: 'Enterprise (Contact Sales)', disabled: true }
    ]
  })
};
