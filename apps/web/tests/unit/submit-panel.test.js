import { test, expect } from 'vitest';
import '../../static/components/submit-panel.js';
import { createStore } from '../../static/core/store.js';

test('Submit button is always disabled in v0.2.0b', async () => {
  const store = createStore();
  store.update('draft', d => { d.blocking = []; });
  const el = document.createElement('submit-panel');
  el.store = store;
  document.body.appendChild(el);
  await el.updateComplete;
  expect(el.shadowRoot.querySelector('button.submit').disabled).toBe(true);
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
