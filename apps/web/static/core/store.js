const SLICE_NAMES = ['draft', 'session', 'ui', 'errorState'];

function defaultState() {
  return {
    draft: {
      schemaVersion: 1,
      rlsId: null,
      rlsPayload: {
        type: null,
        title: '',
        department: '',
        legalQuestion: '',
        factualBackground: '',
      },
      classification: { type: null, confidence: null },
      cureSteps: [],
      blocking: [],
      warnings: [],
      lastValidated: null,
    },
    session: {
      currentStep: 'intake',
      eventLog: [],
      role: 'requester',
      upn: null,
    },
    ui: {
      blurredFields: new Set(),
      autocorrectSuggestions: [],
      pendingValidation: false,
      validatorAbortController: null,
    },
    errorState: {
      breakerStatus: {},
      validatorFailures: {},
      lastApiError: null,
    },
  };
}

export function createStore() {
  const state = defaultState();
  const listeners = Object.fromEntries(SLICE_NAMES.map(n => [n, new Set()]));

  const store = {
    ...state,
    subscribe(slice, fn) {
      if (!listeners[slice]) throw new Error(`Unknown slice: ${slice}`);
      listeners[slice].add(fn);
      return () => listeners[slice].delete(fn);
    },
    update(slice, mutator) {
      if (!listeners[slice]) throw new Error(`Unknown slice: ${slice}`);
      mutator(store[slice]);
      for (const fn of listeners[slice]) fn(store[slice]);
    },
  };
  return store;
}
