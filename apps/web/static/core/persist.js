export const KEY_PREFIX = 'rls-apex.draft.v1';
const CURRENT_SCHEMA = 1;

function keyFor(upn) {
  if (!upn) throw new Error('persist: store.session.upn must be set before hydrate/attachAutoSave');
  return `${KEY_PREFIX}.${upn}`;
}

export function hydrate(store) {
  const raw = localStorage.getItem(keyFor(store.session.upn));
  if (!raw) return { status: 'empty' };

  let parsed;
  try { parsed = JSON.parse(raw); }
  catch { localStorage.removeItem(keyFor(store.session.upn)); return { status: 'malformed-dropped' }; }

  if (parsed.schemaVersion !== CURRENT_SCHEMA) {
    localStorage.removeItem(keyFor(store.session.upn));
    return { status: 'schema-mismatch-dropped' };
  }

  store.update('draft', d => { Object.assign(d, parsed); });
  return { status: 'hydrated' };
}

export function attachAutoSave(store, { debounceMs = 250 } = {}) {
  let timer = null;
  store.subscribe('draft', () => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      localStorage.setItem(keyFor(store.session.upn), JSON.stringify(store.draft));
    }, debounceMs);
  });
}
