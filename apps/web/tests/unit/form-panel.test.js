import { test, expect } from 'vitest';
import '../../static/components/form-panel.js';
import { createStore } from '../../static/core/store.js';

test('shows inline error only for blurred fields', async () => {
  const store = createStore();
  const el = document.createElement('form-panel');
  el.store = store;
  el.surface = { fieldErrors: { title: 'too long' }, banners: [] };
  document.body.appendChild(el);
  await el.updateComplete;
  expect(el.shadowRoot.textContent).toMatch(/too long/);
});

test('typing in field updates store.draft.rlsPayload', async () => {
  const store = createStore();
  const el = document.createElement('form-panel');
  el.store = store;
  el.surface = { fieldErrors: {}, banners: [] };
  document.body.appendChild(el);
  await el.updateComplete;
  const input = el.shadowRoot.querySelector('input[data-field=title]');
  input.value = 'New';
  input.dispatchEvent(new Event('input'));
  expect(store.draft.rlsPayload.title).toBe('New');
});

test('blur adds field to ui.blurredFields', async () => {
  const store = createStore();
  const el = document.createElement('form-panel');
  el.store = store;
  el.surface = { fieldErrors: {}, banners: [] };
  document.body.appendChild(el);
  await el.updateComplete;
  const input = el.shadowRoot.querySelector('input[data-field=title]');
  input.dispatchEvent(new Event('blur'));
  expect(store.ui.blurredFields.has('title')).toBe(true);
});

test('autocorrect Apply mutates rlsPayload', async () => {
  const store = createStore();
  store.update('ui', u => { u.autocorrectSuggestions = [{ ruleId: 'subject-trim', field: 'title', currentValue: 'X', proposedValue: 'X-trim', reason: 'r' }]; });
  store.update('draft', d => { d.rlsPayload.title = 'X'; });
  const el = document.createElement('form-panel');
  el.store = store;
  el.surface = { fieldErrors: {}, banners: [] };
  document.body.appendChild(el);
  await el.updateComplete;
  const apply = [...el.shadowRoot.querySelectorAll('button')].find(b => b.textContent.match(/Apply/));
  apply.click();
  expect(store.draft.rlsPayload.title).toBe('X-trim');
});
