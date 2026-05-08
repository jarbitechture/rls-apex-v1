const FRESH_FAILURE_WINDOW_MS = 30_000;

export function computeSurface({ blocking, blurredFields, breakerStatus, validatorFailures }) {
  const fieldErrors = {};
  for (const issue of blocking || []) {
    if (issue.field && blurredFields.has(issue.field)) {
      fieldErrors[issue.field] = issue.message;
    }
  }

  const banners = [];
  for (const [name, state] of Object.entries(breakerStatus || {})) {
    if (state === 'open') banners.push({ kind: 'breaker-open', name });
  }
  for (const [tool, info] of Object.entries(validatorFailures || {})) {
    if (Date.now() - info.ts < FRESH_FAILURE_WINDOW_MS) {
      banners.push({ kind: 'validator-unavailable', tool });
    }
  }

  return { fieldErrors, banners };
}

export function attachSmartSurface(store, applyDerived) {
  function compute() {
    const surface = computeSurface({
      blocking: store.draft.blocking,
      blurredFields: store.ui.blurredFields,
      breakerStatus: store.errorState.breakerStatus,
      validatorFailures: store.errorState.validatorFailures,
    });
    applyDerived(surface);
  }
  store.subscribe('draft', compute);
  store.subscribe('ui', compute);
  store.subscribe('errorState', compute);
  compute();
}
