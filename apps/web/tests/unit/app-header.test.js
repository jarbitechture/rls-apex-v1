import { test, expect } from 'vitest';
import '../../static/components/app-header.js';
import { createStore } from '../../static/core/store.js';

test('role dropdown reflects session.role and updates on change', async () => {
  const store = createStore();
  store.session.role = 'requester';
  store.session.upn = 'a@b.com';
  const el = document.createElement('app-header');
  el.store = store;
  document.body.appendChild(el);
  await el.updateComplete;
  const sel = el.shadowRoot.querySelector('select');
  expect(sel.value).toBe('requester');
  sel.value = 'cao';
  sel.dispatchEvent(new Event('change'));
  expect(store.session.role).toBe('cao');
});

test('renders banners from surface prop', async () => {
  const store = createStore();
  store.session.upn = 'a@b.com';
  const el = document.createElement('app-header');
  el.store = store;
  el.surface = { banners: [{ kind: 'breaker-open', name: 'sidecar' }], fieldErrors: {} };
  document.body.appendChild(el);
  await el.updateComplete;
  expect(el.shadowRoot.textContent).toMatch(/breaker.*open|unavailable/i);
});
