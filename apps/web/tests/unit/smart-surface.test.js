import { test, expect } from 'vitest';
import { computeSurface, breakersToMap } from '../../static/core/automation/smart-surface.js';

// GAP-3 (#41 parity audit): /api/health/breakers returns a list
// {breakers:[{name,state,...}]}; smart-surface expects a {name:state} map.
// rls-shell stored the raw list, so the breaker-open banner was dead code.
test('breakersToMap converts the /api/health/breakers list to a {name:state} map', () => {
  expect(breakersToMap([
    { name: 'roi_sidecar', state: 'open' },
    { name: 'db', state: 'closed' },
  ])).toEqual({ roi_sidecar: 'open', db: 'closed' });
});

test('breakersToMap passes through an already-map shape and tolerates nullish', () => {
  expect(breakersToMap({ sidecar: 'open' })).toEqual({ sidecar: 'open' });
  expect(breakersToMap(null)).toEqual({});
  expect(breakersToMap(undefined)).toEqual({});
});

test('breaker-open banner fires from the real list-shaped breaker payload', () => {
  const out = computeSurface({
    blocking: [], blurredFields: new Set(),
    breakerStatus: breakersToMap([{ name: 'roi_sidecar', state: 'open' }]),
    validatorFailures: {},
  });
  expect(out.banners.some(b => b.kind === 'breaker-open' && b.name === 'roi_sidecar')).toBe(true);
});

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
