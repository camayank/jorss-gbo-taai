/** @type { import('@storybook/html').Preview } */

// Import the design system CSS
import '../src/web/static/css/core/variables.css';
import '../src/web/static/css/core/reset.css';
import '../src/web/static/css/core/typography.css';
import '../src/web/static/css/core/layout.css';
import '../src/web/static/css/core/animations.css';
import '../src/web/static/css/components/buttons.css';
import '../src/web/static/css/components/cards.css';
import '../src/web/static/css/components/forms.css';
import '../src/web/static/css/components/modals.css';
import '../src/web/static/css/components/navigation.css';
import '../src/web/static/css/components/tables.css';
import '../src/web/static/css/components/toast.css';
import '../src/web/static/css/unified-theme.css';

const preview = {
  parameters: {
    actions: { argTypesRegex: '^on[A-Z].*' },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i
      }
    },
    backgrounds: {
      default: 'light',
      values: [
        { name: 'light', value: '#f9fafb' },
        { name: 'dark', value: '#111827' },
        { name: 'white', value: '#ffffff' }
      ]
    },
    viewport: {
      viewports: {
        mobile: { name: 'Mobile', styles: { width: '375px', height: '667px' } },
        tablet: { name: 'Tablet', styles: { width: '768px', height: '1024px' } },
        desktop: { name: 'Desktop', styles: { width: '1280px', height: '800px' } }
      }
    }
  },
  decorators: [
    (Story) => {
      const container = document.createElement('div');
      container.style.padding = '1rem';
      container.innerHTML = Story();
      return container;
    }
  ]
};

export default preview;
