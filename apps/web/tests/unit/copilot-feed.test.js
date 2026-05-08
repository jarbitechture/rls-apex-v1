import { test, expect } from 'vitest';
import '../../static/components/copilot-feed.js';
import { createStore } from '../../static/core/store.js';

test('renders eventLog newest-first', async () => {
  const store = createStore();
  store.update('session', s => { s.eventLog = [
    { ts: 1, tool: 'classify_matter', summary: 'old' },
    { ts: 2, tool: 'validate_rls_structure', summary: 'new' },
  ]; });
  const el = document.createElement('copilot-feed');
  el.store = store;
  document.body.appendChild(el);
  await el.updateComplete;
  const items = el.shadowRoot.querySelectorAll('.entry');
  expect(items[0].textContent).toMatch(/new/);
  expect(items[1].textContent).toMatch(/old/);
});

test('shows truncation indicator above 200 events', async () => {
  const store = createStore();
  store.update('session', s => {
    s.eventLog = Array.from({ length: 220 }, (_, i) => ({ ts: i, tool: 't', summary: `e${i}` }));
  });
  const el = document.createElement('copilot-feed');
  el.store = store;
  document.body.appendChild(el);
  await el.updateComplete;
  expect(el.shadowRoot.textContent).toMatch(/older events truncated/i);
});
