import { test, expect } from 'vitest';
import '../../static/components/status-panel.js';
import { createStore } from '../../static/core/store.js';

test('NeedsFixes narrative when blocking present', async () => {
  const store = createStore();
  store.update('draft', d => { d.blocking = [{ code: 'X', message: 'm1' }, { code: 'Y', message: 'm2' }]; });
  const el = document.createElement('status-panel');
  el.store = store; el.surface = { fieldErrors: {}, banners: [] };
  document.body.appendChild(el);
  await el.updateComplete;
  expect(el.shadowRoot.textContent).toMatch(/Needs fixes.*2/);
});

test('Ready narrative when no blocking', async () => {
  const store = createStore();
  store.update('draft', d => { d.blocking = []; d.lastValidated = Date.now(); });
  const el = document.createElement('status-panel');
  el.store = store; el.surface = { fieldErrors: {}, banners: [] };
  document.body.appendChild(el);
  await el.updateComplete;
  expect(el.shadowRoot.textContent).toMatch(/Ready for CAO/);
});
