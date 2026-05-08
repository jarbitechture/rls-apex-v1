const STEPS = ['intake', 'form', 'status', 'cure', 'submit'];

export function parseLocation(loc = window.location) {
  const path = loc.pathname || '/';
  const m = path.match(/^\/cao\/([^/]+)/);
  if (m) return { view: 'cao', rlsId: m[1] };

  const hashStep = (loc.hash || '').match(/^#step=(\w+)/);
  const step = hashStep && STEPS.includes(hashStep[1]) ? hashStep[1] : 'intake';
  return { view: 'requester', step };
}

export function navigateToStep(step, loc = window.location) {
  if (!STEPS.includes(step)) throw new Error(`Unknown step: ${step}`);
  loc.hash = `#step=${step}`;
}

export function attachRouter(store) {
  function update() {
    const r = parseLocation();
    if (r.view === 'requester') {
      store.update('session', s => { s.currentStep = r.step; });
    }
  }
  window.addEventListener('hashchange', update);
  window.addEventListener('popstate', update);
  update();  // initial
}

export const ALL_STEPS = STEPS;
