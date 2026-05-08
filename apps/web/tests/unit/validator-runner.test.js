import { test, expect, vi, beforeEach } from 'vitest';
import { createStore } from '../../static/core/store.js';
import { attachValidatorRunner } from '../../static/core/automation/validator-runner.js';

let postValidateMock;

beforeEach(() => {
  postValidateMock = vi.fn(async (body, signal) => {
    if (signal?.aborted) {
      const e = new Error('aborted'); e.name = 'AbortError'; throw e;
    }
    return { blocking: [], warnings: [], cureSteps: [] };
  });
});

test('rapid edits trigger only one trailing call after debounce', async () => {
  const store = createStore();
  attachValidatorRunner(store, { postValidate: postValidateMock, debounceMs: 30 });
  store.update('draft', d => { d.rlsPayload.title = '1'; });
  store.update('draft', d => { d.rlsPayload.title = '2'; });
  store.update('draft', d => { d.rlsPayload.title = '3'; });
  await new Promise(r => setTimeout(r, 80));
  expect(postValidateMock).toHaveBeenCalledTimes(1);
});

test('new fire aborts previous in-flight request', async () => {
  let resolveFirst, abortedSignal = null;
  postValidateMock = vi.fn((body, signal) => new Promise((resolve, reject) => {
    if (postValidateMock.mock.calls.length === 1) {
      signal.addEventListener('abort', () => { abortedSignal = true; reject(Object.assign(new Error('abort'), { name: 'AbortError' })); });
      resolveFirst = resolve;
    } else {
      resolve({ blocking: [], warnings: [], cureSteps: [] });
    }
  }));
  const store = createStore();
  attachValidatorRunner(store, { postValidate: postValidateMock, debounceMs: 10 });
  store.update('draft', d => { d.rlsPayload.title = 'a'; });
  await new Promise(r => setTimeout(r, 30));
  store.update('draft', d => { d.rlsPayload.title = 'b'; });
  await new Promise(r => setTimeout(r, 60));
  expect(abortedSignal).toBe(true);
});

test('successful response writes blocking + warnings + lastValidated + appends eventLog', async () => {
  postValidateMock = vi.fn(async () => ({ blocking: [{ code: 'X' }], warnings: [], cureSteps: [] }));
  const store = createStore();
  attachValidatorRunner(store, { postValidate: postValidateMock, debounceMs: 10 });
  store.update('draft', d => { d.rlsPayload.title = 'a'; });
  await new Promise(r => setTimeout(r, 50));
  expect(store.draft.blocking).toHaveLength(1);
  expect(store.draft.lastValidated).toBeTruthy();
  expect(store.session.eventLog).toHaveLength(1);
  expect(store.session.eventLog[0].tool).toBe('validate_rls_structure');
});
