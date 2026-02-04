/**
 * PostCSS Configuration
 *
 * Used for CSS processing and bundling.
 * Works with Vite build or can be used standalone.
 *
 * Standalone usage:
 *   npx postcss src/web/static/css/main.css -o dist/css/main.min.css
 */

module.exports = {
  plugins: {
    // Import CSS files using @import
    'postcss-import': {},

    // Modern CSS features transpilation
    'postcss-preset-env': {
      stage: 2,
      features: {
        'nesting-rules': true,
        'custom-properties': true,
        'custom-media-queries': true,
      },
      autoprefixer: {
        grid: true,
      },
    },

    // Autoprefixer for browser compatibility
    'autoprefixer': {},

    // Minification (production only)
    ...(process.env.NODE_ENV === 'production' ? {
      'cssnano': {
        preset: ['default', {
          // Remove all comments
          discardComments: {
            removeAll: true,
          },
          // Normalize whitespace
          normalizeWhitespace: true,
          // Merge rules
          mergeRules: true,
          // Minify selectors
          minifySelectors: true,
          // Minify params
          minifyParams: true,
          // Optimize font values
          minifyFontValues: true,
          // Normalize string quotes
          normalizeString: true,
        }],
      },
    } : {}),
  },
};
