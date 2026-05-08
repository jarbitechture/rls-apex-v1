import { test, expect } from 'vitest';
import { computeSurface } from '../../static/core/automation/smart-surface.js';

test('inline lint hidden for non-blurred fields', () => {
  const out = computeSurface({
    blocking: [{ field: 'title', message: 'too long' }],
    blurredFields: new Set(),
    breakerStatus: {}, validatorFailures: {},
  });
  expect(out.fieldErrors.title).toBeUndefined();
});

test('inline lint visible for blurred fields', () => {
  const out = computeSurface({
    blocking: [{ field: 'title', message: 'too long' }],
    blurredFields: new Set(['title']),
    breakerStatus: {}, validatorFailures: {},
  });
  expect(out.fieldErrors.title).toBe('too long');
});

test('breaker open surfaces top banner', () => {
  const out = computeSurface({
    blocking: [], blurredFields: new Set(),
    breakerStatus: { sidecar: 'open' }, validatorFailures: {},
  });
  expect(out.banners.some(b => b.kind === 'breaker-open')).toBe(true);
});

test('fresh validator failure surfaces validator-unavailable banner', () => {
  const out = computeSurface({
    blocking: [], blurredFields: new Set(), breakerStatus: {},
    validatorFailures: { validate_rls_structure: { ts: Date.now() } },
  });
  expect(out.banners.some(b => b.kind === 'validator-unavailable')).toBe(true);
});

test('stale (>30s) validator failure does NOT surface banner', () => {
  const out = computeSurface({
    blocking: [], blurredFields: new Set(), breakerStatus: {},
    validatorFailures: { validate_rls_structure: { ts: Date.now() - 31_000 } },
  });
  expect(out.banners.some(b => b.kind === 'validator-unavailable')).toBe(false);
});
