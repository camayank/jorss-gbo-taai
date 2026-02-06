/**
 * Button Component Stories
 *
 * Demonstrates all button variants, sizes, and states.
 */

export default {
  title: 'Components/Buttons/Button',
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'select',
      options: ['primary', 'secondary', 'accent', 'ghost', 'outline', 'danger', 'success', 'warning', 'link'],
      description: 'Visual style variant'
    },
    size: {
      control: 'select',
      options: ['xs', 'sm', 'md', 'lg', 'xl'],
      description: 'Button size'
    },
    disabled: {
      control: 'boolean',
      description: 'Disabled state'
    },
    loading: {
      control: 'boolean',
      description: 'Loading state with spinner'
    },
    fullWidth: {
      control: 'boolean',
      description: 'Full width button'
    }
  }
};

// Helper to create button HTML
const createButton = ({ text = 'Button', variant = 'primary', size = 'md', disabled = false, loading = false, fullWidth = false, icon = '' }) => {
  const sizeClass = size !== 'md' ? `btn-${size}` : '';
  const variantClass = `btn-${variant}`;
  const loadingClass = loading ? 'btn-loading' : '';
  const widthClass = fullWidth ? 'btn-full' : '';

  return `
    <button
      type="button"
      class="btn ${variantClass} ${sizeClass} ${loadingClass} ${widthClass}"
      ${disabled || loading ? 'disabled' : ''}
    >
      ${loading ? '<span class="btn-spinner"></span>' : ''}
      ${icon ? `<span class="btn-icon btn-icon-left">${icon}</span>` : ''}
      <span class="btn-text">${text}</span>
    </button>
  `;
};

// Primary Button
export const Primary = {
  args: {
    text: 'Primary Button',
    variant: 'primary',
    size: 'md'
  },
  render: (args) => createButton(args)
};

// Secondary Button
export const Secondary = {
  args: {
    text: 'Secondary Button',
    variant: 'secondary',
    size: 'md'
  },
  render: (args) => createButton(args)
};

// Accent Button (Teal CTA)
export const Accent = {
  args: {
    text: 'Accent Button',
    variant: 'accent',
    size: 'md'
  },
  render: (args) => createButton(args)
};

// Ghost Button
export const Ghost = {
  args: {
    text: 'Ghost Button',
    variant: 'ghost',
    size: 'md'
  },
  render: (args) => createButton(args)
};

// Outline Button
export const Outline = {
  args: {
    text: 'Outline Button',
    variant: 'outline',
    size: 'md'
  },
  render: (args) => createButton(args)
};

// Danger Button
export const Danger = {
  args: {
    text: 'Delete',
    variant: 'danger',
    size: 'md'
  },
  render: (args) => createButton(args)
};

// Success Button
export const Success = {
  args: {
    text: 'Confirm',
    variant: 'success',
    size: 'md'
  },
  render: (args) => createButton(args)
};

// All Sizes
export const AllSizes = {
  render: () => `
    <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
      ${createButton({ text: 'Extra Small', variant: 'primary', size: 'xs' })}
      ${createButton({ text: 'Small', variant: 'primary', size: 'sm' })}
      ${createButton({ text: 'Medium', variant: 'primary', size: 'md' })}
      ${createButton({ text: 'Large', variant: 'primary', size: 'lg' })}
      ${createButton({ text: 'Extra Large', variant: 'primary', size: 'xl' })}
    </div>
  `
};

// All Variants
export const AllVariants = {
  render: () => `
    <div style="display: flex; flex-wrap: wrap; gap: 12px;">
      ${createButton({ text: 'Primary', variant: 'primary' })}
      ${createButton({ text: 'Secondary', variant: 'secondary' })}
      ${createButton({ text: 'Accent', variant: 'accent' })}
      ${createButton({ text: 'Ghost', variant: 'ghost' })}
      ${createButton({ text: 'Outline', variant: 'outline' })}
      ${createButton({ text: 'Danger', variant: 'danger' })}
      ${createButton({ text: 'Success', variant: 'success' })}
      ${createButton({ text: 'Warning', variant: 'warning' })}
      ${createButton({ text: 'Link', variant: 'link' })}
    </div>
  `
};

// Disabled State
export const Disabled = {
  args: {
    text: 'Disabled Button',
    variant: 'primary',
    disabled: true
  },
  render: (args) => createButton(args)
};

// Loading State
export const Loading = {
  args: {
    text: 'Loading...',
    variant: 'primary',
    loading: true
  },
  render: (args) => createButton(args)
};

// Full Width
export const FullWidth = {
  args: {
    text: 'Full Width Button',
    variant: 'primary',
    fullWidth: true
  },
  render: (args) => `
    <div style="max-width: 400px;">
      ${createButton(args)}
    </div>
  `
};

// With Icon
export const WithIcon = {
  render: () => `
    <div style="display: flex; gap: 12px; flex-wrap: wrap;">
      ${createButton({
        text: 'Add Item',
        variant: 'primary',
        icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>'
      })}
      ${createButton({
        text: 'Download',
        variant: 'accent',
        icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>'
      })}
      ${createButton({
        text: 'Delete',
        variant: 'danger',
        icon: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>'
      })}
    </div>
  `
};

// Button Group
export const ButtonGroup = {
  render: () => `
    <div style="display: flex; flex-direction: column; gap: 24px;">
      <div>
        <p style="margin-bottom: 8px; color: #6b7280; font-size: 14px;">Horizontal Group</p>
        <div class="btn-group">
          ${createButton({ text: 'Left', variant: 'outline' })}
          ${createButton({ text: 'Center', variant: 'outline' })}
          ${createButton({ text: 'Right', variant: 'outline' })}
        </div>
      </div>
      <div>
        <p style="margin-bottom: 8px; color: #6b7280; font-size: 14px;">Connected Group</p>
        <div class="btn-group btn-group-connected">
          ${createButton({ text: 'Day', variant: 'outline' })}
          ${createButton({ text: 'Week', variant: 'primary' })}
          ${createButton({ text: 'Month', variant: 'outline' })}
        </div>
      </div>
    </div>
  `
};
