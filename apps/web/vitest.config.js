import { defineConfig } from 'vitest/config';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  test: {
    environment: 'happy-dom',
    include: ['tests/unit/**/*.test.js'],
    alias: {
      lit: path.resolve(__dirname, 'static/lib/lit-3.2.1.min.js'),
    },
  },
});
