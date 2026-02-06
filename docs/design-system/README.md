# TaxFlow Design System

A unified design system for the Jorss-Gbo tax platform, ensuring visual consistency across all portals (Admin, CPA, Public).

## Quick Start

```html
<!-- Single import for complete design system -->
<link rel="stylesheet" href="/static/css/main.css">

<!-- Or import individual modules -->
<link rel="stylesheet" href="/static/css/core/variables.css">
<link rel="stylesheet" href="/static/css/core/reset.css">
<link rel="stylesheet" href="/static/css/core/typography.css">
```

## Design Tokens

All design decisions are encoded as CSS custom properties in `core/variables.css`.

### Colors

| Token | Value | Usage |
|-------|-------|-------|
| `--color-primary-500` | `#1e3a5f` | Primary brand color (Navy) |
| `--color-accent-500` | `#14b8a6` | Accent/CTA color (Teal) |
| `--color-success-500` | `#10b981` | Success states |
| `--color-warning-500` | `#f59e0b` | Warning states |
| `--color-error-500` | `#ef4444` | Error states |
| `--color-info-500` | `#3b82f6` | Informational |

### Spacing

8px base unit system:

| Token | Value | Pixels |
|-------|-------|--------|
| `--space-1` | `0.25rem` | 4px |
| `--space-2` | `0.5rem` | 8px |
| `--space-3` | `0.75rem` | 12px |
| `--space-4` | `1rem` | 16px |
| `--space-5` | `1.25rem` | 20px |
| `--space-6` | `1.5rem` | 24px |
| `--space-8` | `2rem` | 32px |

### Typography

| Token | Value | Usage |
|-------|-------|-------|
| `--text-xs` | `0.75rem` | 12px - Labels |
| `--text-sm` | `0.875rem` | 14px - Body small |
| `--text-base` | `1rem` | 16px - Body |
| `--text-lg` | `1.125rem` | 18px - Large body |
| `--text-xl` | `1.25rem` | 20px - Subheadings |
| `--text-2xl` | `1.5rem` | 24px - Headings |
| `--text-3xl` | `1.875rem` | 30px - Page titles |

### Breakpoints

| Token | Value | Usage |
|-------|-------|-------|
| `--breakpoint-xs` | `320px` | Small phones |
| `--breakpoint-sm` | `480px` | Phones |
| `--breakpoint-md` | `768px` | Tablets |
| `--breakpoint-lg` | `1024px` | Laptops |
| `--breakpoint-xl` | `1280px` | Desktops |

## Themes

Apply themes using the `data-theme` attribute on `<html>`:

```html
<!-- Public pages (light theme) -->
<html data-theme="public">

<!-- CPA portal (light, professional) -->
<html data-theme="cpa">

<!-- Admin portal (dark theme) -->
<html data-theme="admin">
```

## Components

### Buttons

```html
<button class="btn btn-primary">Primary Action</button>
<button class="btn btn-secondary">Secondary</button>
<button class="btn btn-ghost">Ghost</button>
<button class="btn btn-primary btn-loading">Loading...</button>
```

### Forms

```html
<div class="form-group">
  <label class="form-label required">Email</label>
  <input type="email" class="form-input" required>
  <span class="form-feedback form-feedback-error">Invalid email</span>
</div>
```

### Cards

```html
<div class="card">
  <div class="card-header">
    <h3 class="card-title">Title</h3>
  </div>
  <div class="card-body">Content</div>
  <div class="card-footer">Actions</div>
</div>
```

### Alerts

```html
<div class="alert alert-success">
  <span class="alert-icon">✓</span>
  <div class="alert-content">
    <div class="alert-title">Success!</div>
    Your changes have been saved.
  </div>
</div>
```

## Feedback States

### Loading Spinner

```html
<span class="spinner"></span>
<span class="spinner spinner-lg"></span>
<button class="btn btn-primary btn-loading">Saving...</button>
```

### Skeleton Loading

```html
<div class="skeleton skeleton-title"></div>
<div class="skeleton skeleton-text"></div>
<div class="skeleton skeleton-text"></div>
```

### Toast Notifications

```html
<div class="toast toast-success">
  <span class="toast-icon">✓</span>
  <div class="toast-content">
    <div class="toast-title">Saved</div>
    <div class="toast-message">Your changes have been saved.</div>
  </div>
</div>
```

### Progress Bar

```html
<div class="progress">
  <div class="progress-bar" style="width: 60%"></div>
</div>
```

## Responsive Utilities

### Display

```html
<div class="hide-mobile">Desktop only</div>
<div class="hide-desktop">Mobile only</div>
<div class="hidden-md">Hidden on tablets</div>
```

### Grid

```html
<div class="grid grid-cols-3 md:grid-cols-2 sm:grid-cols-1 gap-4">
  <div>Column</div>
  <div>Column</div>
  <div>Column</div>
</div>
```

### Flex

```html
<div class="flex items-center justify-between gap-4">
  <div>Left</div>
  <div>Right</div>
</div>
```

## Accessibility

### Focus States

All interactive elements have visible focus indicators by default.

```css
:focus-visible {
  outline: 2px solid var(--color-primary-500);
  outline-offset: 2px;
}
```

### Screen Reader

```html
<span class="sr-only">Screen reader only text</span>
<a href="#main" class="skip-link">Skip to main content</a>
```

### Touch Targets

Minimum 44x44px for WCAG compliance:

```html
<button class="btn touch-target">Accessible Button</button>
```

### Reduced Motion

The design system respects `prefers-reduced-motion`:

```css
@media (prefers-reduced-motion: reduce) {
  * { animation-duration: 0.01ms !important; }
}
```

## Jinja2 Components

Use reusable Jinja2 macros from `templates/components/`:

```jinja2
{% from 'components/feedback/alert.html' import alert %}
{% from 'components/layout/card.html' import card %}

{{ alert(type='success', title='Saved', message='Changes saved.') }}

{% call card(title='User Profile') %}
  Content goes here
{% endcall %}
```

## File Structure

```
src/web/static/css/
├── main.css              # Single entry point
├── core/
│   ├── variables.css     # Design tokens
│   ├── reset.css         # Normalize
│   ├── typography.css    # Text styles
│   ├── layout.css        # Grid, containers
│   ├── responsive.css    # Breakpoint utilities
│   ├── accessibility.css # A11y utilities
│   └── feedback.css      # Loading, toasts
└── components/
    ├── buttons.css
    ├── cards.css
    ├── forms.css
    ├── tables.css
    └── navigation.css
```

## Browser Support

- Chrome (latest 2 versions)
- Firefox (latest 2 versions)
- Safari (latest 2 versions + iOS)
- Edge (latest 2 versions)

## Contributing

1. Use design tokens from `variables.css` - never hardcode colors/spacing
2. Follow BEM-style naming for new components
3. Ensure WCAG 2.1 AA compliance
4. Test at all breakpoints (320px, 480px, 768px, 1024px, 1280px)
5. Add stories to Storybook for new components
