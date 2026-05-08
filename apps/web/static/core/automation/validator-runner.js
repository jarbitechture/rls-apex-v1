export function attachValidatorRunner(store, { postValidate, debounceMs = 750 } = {}) {
  if (!postValidate) throw new Error('postValidate required');
  let timer = null;

  store.subscribe('draft', () => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => fire(), debounceMs);
  });

  async function fire() {
    if (store.ui.validatorAbortController) {
      store.ui.validatorAbortController.abort();
    }
    const ctrl = new AbortController();
    store.update('ui', u => {
      u.validatorAbortController = ctrl;
      u.pendingValidation = true;
    });

    try {
      const result = await postValidate({ rlsPayload: store.draft.rlsPayload }, ctrl.signal);
      store.update('draft', d => {
        d.blocking = result.blocking || [];
        d.warnings = result.warnings || [];
        d.cureSteps = result.cureSteps || [];
        d.lastValidated = Date.now();
      });
      store.update('session', s => {
        s.eventLog.push({
          ts: Date.now(),
          tool: 'validate_rls_structure',
          summary: `${result.blocking?.length ?? 0} blocking, ${result.warnings?.length ?? 0} warnings`,
        });
        if (s.eventLog.length > 200) s.eventLog = s.eventLog.slice(-200);
      });
    } catch (err) {
      if (err.name === 'AbortError') return;  // newer request supersedes
      store.update('errorState', e => {
        e.lastApiError = String(err);
        e.validatorFailures.validate_rls_structure = { ts: Date.now(), message: String(err) };
      });
    } finally {
      store.update('ui', u => {
        if (u.validatorAbortController === ctrl) {
          u.validatorAbortController = null;
        }
        u.pendingValidation = false;
      });
    }
  }
}
