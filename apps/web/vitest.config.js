import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // jsdom over happy-dom: happy-dom escapes Lit directive markers in
    // .map(html``) array contexts, breaking template arrays. jsdom handles
    // them correctly.
    environment: 'jsdom',
    include: ['tests/unit/**/*.test.js'],
  },
});
