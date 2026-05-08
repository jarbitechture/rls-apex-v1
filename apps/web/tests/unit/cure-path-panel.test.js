import { test, expect } from 'vitest';
import '../../static/components/cure-path-panel.js';
import { createStore } from '../../static/core/store.js';

test('renders cure steps with disabled Mark Done', async () => {
  const store = createStore();
  store.update('draft', d => {
    d.cureSteps = [{ step: 1, title: 'Attach approval', instruction: 'Upload the doc',
                     references: [{ label: 'LDC §6.4', citation: 'LDC §6.4', source: 'ldc' }] }];
  });
  const el = document.createElement('cure-path-panel');
  el.store = store;
  document.body.appendChild(el);
  await el.updateComplete;
  expect(el.shadowRoot.textContent).toMatch(/Attach approval/);
  const btn = el.shadowRoot.querySelector('button.mark-done');
  expect(btn.disabled).toBe(true);
});

test('empty state when no cure steps', async () => {
  const el = document.createElement('cure-path-panel');
  el.store = createStore();
  document.body.appendChild(el);
  await el.updateComplete;
  expect(el.shadowRoot.textContent).toMatch(/No cure steps/);
});
