/**
 * Vite Build Configuration for Frontend Asset Bundling
 *
 * This configuration optimizes CSS and JavaScript assets for production:
 * - Bundles multiple CSS files into single minified output
 * - Bundles JavaScript with code splitting for optimal loading
 * - Generates cache-busting hashes for versioning
 * - Tree-shakes unused code
 *
 * Usage:
 *   npm run build        # Production build
 *   npm run build:dev    # Development build (no minification)
 *
 * Output:
 *   dist/
 *     css/
 *       main.[hash].css       # All CSS bundled and minified
 *     js/
 *       main.[hash].js        # Core JavaScript
 *       vendor.[hash].js      # Third-party libraries
 *       chatbot.[hash].js     # Chatbot code (lazy loaded)
 */

import { defineConfig } from 'vite';
import path from 'path';

export default defineConfig({
  // Build configuration
  build: {
    // Output directory
    outDir: 'dist',

    // Asset directory within outDir
    assetsDir: 'assets',

    // Generate source maps for debugging
    sourcemap: process.env.NODE_ENV !== 'production',

    // Minification settings
    minify: process.env.NODE_ENV === 'production' ? 'terser' : false,

    // Terser options for production
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true,
      },
    },

    // CSS code splitting
    cssCodeSplit: false, // Single CSS file for simplicity

    // Rollup options for bundling
    rollupOptions: {
      input: {
        // Core modules
        api: path.resolve(__dirname, 'src/web/static/js/core/api.js'),
        utils: path.resolve(__dirname, 'src/web/static/js/core/utils.js'),
        validation: path.resolve(__dirname, 'src/web/static/js/core/validation.js'),
        // Feature modules
        chatbot: path.resolve(__dirname, 'src/web/static/js/chatbot-ux-enhancements.js'),
        // Page modules
        'cpa-dashboard': path.resolve(__dirname, 'src/web/static/js/pages/cpa-dashboard.js'),
        'tax-form': path.resolve(__dirname, 'src/web/static/js/pages/tax-form.js'),
      },

      output: {
        // Entry chunk naming
        entryFileNames: 'js/[name].[hash].js',

        // Dynamic import chunk naming
        chunkFileNames: 'js/[name].[hash].js',

        // Asset naming (CSS, images, etc.)
        assetFileNames: (assetInfo) => {
          const extType = assetInfo.name.split('.').pop();
          if (/css/i.test(extType)) {
            return 'css/[name].[hash][extname]';
          }
          if (/png|jpe?g|svg|gif|tiff|bmp|ico/i.test(extType)) {
            return 'images/[name].[hash][extname]';
          }
          if (/woff|woff2|eot|ttf|otf/i.test(extType)) {
            return 'fonts/[name].[hash][extname]';
          }
          return 'assets/[name].[hash][extname]';
        },

        // Manual chunk configuration for code splitting
        manualChunks: (id) => {
          // Vendor chunk for node_modules
          if (id.includes('node_modules')) {
            return 'vendor';
          }

          // Chatbot features as separate chunk
          if (id.includes('chatbot') || id.includes('advisor')) {
            return 'chatbot';
          }
        },
      },
    },

    // Asset size warnings
    chunkSizeWarningLimit: 500, // KB
  },

  // CSS configuration
  css: {
    // PostCSS configuration
    postcss: {
      plugins: [
        // Autoprefixer for browser compatibility
        require('autoprefixer'),

        // CSS Nano for minification (production only)
        ...(process.env.NODE_ENV === 'production'
          ? [require('cssnano')({
              preset: ['default', {
                discardComments: { removeAll: true },
                normalizeWhitespace: true,
              }],
            })]
          : []),
      ],
    },
  },

  // Development server (if needed)
  server: {
    port: 5173,
    strictPort: true,
  },

  // Resolve configuration
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src/web/static'),
      '@css': path.resolve(__dirname, 'src/web/static/css'),
      '@js': path.resolve(__dirname, 'src/web/static/js'),
    },
  },

  // Define environment variables
  define: {
    __APP_VERSION__: JSON.stringify(process.env.npm_package_version || '1.0.0'),
    __BUILD_TIME__: JSON.stringify(new Date().toISOString()),
  },
});
