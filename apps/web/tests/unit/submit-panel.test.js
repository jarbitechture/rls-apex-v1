import { test, expect, vi } from 'vitest';
import '../../static/components/submit-panel.js';
import { createStore } from '../../static/core/store.js';

test('submit button is enabled and POSTs a content-digest key', async () => {
  const calls = [];
  vi.stubGlobal('fetch', vi.fn(async (url, opts) => {
    calls.push({ url, body: JSON.parse(opts.body) });
    return { ok: true, json: async () => ({ rls_id: 'RLS-26-0001',
      lineage_receipt: { sequence: 1, this_hash: 'a'.repeat(64) } }) };
  }));
  const store = createStore();
  store.update('draft', d => { d.rlsPayload = { subject: 'Lease', department: 'Legal' }; });
  const el = document.createElement('submit-panel');
  el.store = store;
  document.body.appendChild(el);
  await el.updateComplete;
  const btn = el.shadowRoot.querySelector('button.submit');
  expect(btn.disabled).toBe(false);
  btn.click();
  await new Promise(r => setTimeout(r, 0));
  expect(calls[0].url).toBe('/api/rls/submit');
  expect(calls[0].body.idempotency_key).toMatch(/^[0-9a-f]{64}$/);
  // stable: same draft -> same key
  const k1 = calls[0].body.idempotency_key;
  btn.click(); await new Promise(r => setTimeout(r, 0));
  expect(calls[1].body.idempotency_key).toBe(k1);
});

test('JSON copy block renders rlsPayload', async () => {
  const store = createStore();
  store.update('draft', d => { d.rlsPayload = { title: 'X', department: 'Y', legalQuestion: '', factualBackground: '' }; });
  const el = document.createElement('submit-panel');
  el.store = store;
  document.body.appendChild(el);
  await el.updateComplete;
  expect(el.shadowRoot.querySelector('pre').textContent).toMatch(/"title": "X"/);
});
