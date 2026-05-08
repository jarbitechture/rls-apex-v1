import { test, expect, vi } from 'vitest';
import '../../static/components/intake-panel.js';
import { createStore } from '../../static/core/store.js';

test('Draft RLS button posts to /api/intake and populates rlsPayload', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true, json: async () => ({ classification: { type: 'permit_or_zoning' }, rlsPayload: { title: 'drafted' } }),
  })));
  const store = createStore();
  store.session.upn = 'a@b.com';
  const el = document.createElement('intake-panel');
  el.store = store;
  document.body.appendChild(el);
  await el.updateComplete;
  const ta = el.shadowRoot.querySelector('textarea');
  ta.value = 'permit denial';
  ta.dispatchEvent(new Event('input'));
  el.shadowRoot.querySelector('button.primary').click();
  await new Promise(r => setTimeout(r, 30));
  expect(store.draft.rlsPayload.title).toBe('drafted');
  expect(store.draft.classification.type).toBe('permit_or_zoning');
});

test('paste-skip toggle reveals structured fields', async () => {
  const el = document.createElement('intake-panel');
  el.store = createStore();
  document.body.appendChild(el);
  await el.updateComplete;
  const toggle = el.shadowRoot.querySelector('input[type=checkbox]');
  toggle.checked = true;
  toggle.dispatchEvent(new Event('change'));
  await el.updateComplete;
  expect(el.shadowRoot.querySelectorAll('input[data-field]').length).toBeGreaterThan(0);
});
