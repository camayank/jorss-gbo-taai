/** @type { import('@storybook/html-vite').StorybookConfig } */
const config = {
  stories: [
    '../src/web/templates/components/**/*.stories.@(js|jsx|ts|tsx)',
    '../stories/**/*.stories.@(js|jsx|ts|tsx)'
  ],
  addons: [
    '@storybook/addon-essentials',
    '@storybook/addon-a11y'
  ],
  framework: {
    name: '@storybook/html-vite',
    options: {}
  },
  staticDirs: ['../src/web/static'],
  docs: {
    autodocs: 'tag'
  }
};

export default config;
