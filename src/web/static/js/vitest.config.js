import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // Use jsdom for DOM testing
    environment: 'jsdom',

    // Test file patterns
    include: ['**/__tests__/**/*.test.js', '**/*.test.js'],

    // Setup files run before each test
    setupFiles: ['./__tests__/setup.js'],

    // Global test utilities
    globals: true,

    // Coverage configuration
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['core/**/*.js', 'alpine/**/*.js'],
      exclude: ['**/__tests__/**', '**/node_modules/**'],
    },

    // Timeout for async tests
    testTimeout: 10000,
  },
});
