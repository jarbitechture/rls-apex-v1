import { test, expect, beforeEach, vi } from 'vitest';
import { createStore } from '../../static/core/store.js';
import { hydrate, attachAutoSave, KEY_PREFIX } from '../../static/core/persist.js';

beforeEach(() => { localStorage.clear(); });

test('hydrate with no key leaves draft default', () => {
  const store = createStore();
  store.session.upn = 'a@b.com';
  hydrate(store);
  expect(store.draft.rlsPayload.title).toBe('');
});

test('hydrate restores valid v1 draft', () => {
  const upn = 'a@b.com';
  localStorage.setItem(`${KEY_PREFIX}.${upn}`, JSON.stringify({
    schemaVersion: 1, rlsId: 'rls-1', rlsPayload: { title: 'T' },
    classification: {}, cureSteps: [], blocking: [], warnings: [], lastValidated: null,
  }));
  const store = createStore();
  store.session.upn = upn;
  const result = hydrate(store);
  expect(result.status).toBe('hydrated');
  expect(store.draft.rlsPayload.title).toBe('T');
});

test('hydrate drops mismatched schemaVersion', () => {
  const upn = 'a@b.com';
  localStorage.setItem(`${KEY_PREFIX}.${upn}`, JSON.stringify({
    schemaVersion: 0, rlsPayload: { title: 'old' },
  }));
  const store = createStore();
  store.session.upn = upn;
  const result = hydrate(store);
  expect(result.status).toBe('schema-mismatch-dropped');
  expect(store.draft.rlsPayload.title).toBe('');
});

test('attachAutoSave persists draft after debounce', async () => {
  const upn = 'a@b.com';
  const store = createStore();
  store.session.upn = upn;
  attachAutoSave(store, { debounceMs: 10 });
  store.update('draft', d => { d.rlsPayload.title = 'auto'; });
  await new Promise(r => setTimeout(r, 50));
  const saved = JSON.parse(localStorage.getItem(`${KEY_PREFIX}.${upn}`));
  expect(saved.rlsPayload.title).toBe('auto');
});
