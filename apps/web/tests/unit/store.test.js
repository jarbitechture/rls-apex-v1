import { test, expect, vi } from 'vitest';
import { createStore } from '../../static/core/store.js';

test('createStore returns the four sliced namespaces', () => {
  const store = createStore();
  expect(store.draft).toBeDefined();
  expect(store.session).toBeDefined();
  expect(store.ui).toBeDefined();
  expect(store.errorState).toBeDefined();
  expect(store.draft.schemaVersion).toBe(1);
});

test('subscribe fires on slice mutation', () => {
  const store = createStore();
  const spy = vi.fn();
  store.subscribe('draft', spy);
  store.update('draft', d => { d.rlsPayload.title = 'X'; });
  expect(spy).toHaveBeenCalledTimes(1);
  expect(spy.mock.calls[0][0].rlsPayload.title).toBe('X');
});

test('subscribe to one slice does not fire on other slice mutation', () => {
  const store = createStore();
  const spy = vi.fn();
  store.subscribe('draft', spy);
  store.update('session', s => { s.currentStep = 'form'; });
  expect(spy).not.toHaveBeenCalled();
});

test('unsubscribe removes the listener', () => {
  const store = createStore();
  const spy = vi.fn();
  const unsub = store.subscribe('draft', spy);
  unsub();
  store.update('draft', d => { d.rlsPayload.title = 'X'; });
  expect(spy).not.toHaveBeenCalled();
});
