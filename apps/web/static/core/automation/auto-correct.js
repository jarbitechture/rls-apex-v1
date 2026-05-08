function trimToWordBoundary(s, max) {
  if (s.length <= max) return s;
  const trimmed = s.slice(0, max);
  const lastSpace = trimmed.lastIndexOf(' ');
  return lastSpace > 0 ? trimmed.slice(0, lastSpace) : trimmed;
}

const subjectTrim = {
  id: 'subject-trim',
  apply(payload) {
    const t = payload.title || '';
    if (t.length <= 50) return null;
    return {
      ruleId: 'subject-trim', field: 'title',
      currentValue: t, proposedValue: trimToWordBoundary(t, 50),
      reason: 'RLS subject must be ≤50 characters',
    };
  },
};

const titleCaseFix = {
  id: 'title-case-fix',
  apply(payload) {
    const t = payload.title || '';
    const words = t.split(' ');
    let changed = false;
    const fixed = words.map(w => {
      if (w.length > 3 && w === w.toUpperCase() && /[A-Z]/.test(w)) {
        changed = true;
        return w[0] + w.slice(1).toLowerCase();
      }
      return w;
    }).join(' ');
    if (!changed) return null;
    return {
      ruleId: 'title-case-fix', field: 'title',
      currentValue: t, proposedValue: fixed,
      reason: 'Title-case avoids appearing as a shouted instruction',
    };
  },
};

const RELATIVE_RE = /\b(yesterday|today|last week|next week|tomorrow)\b/i;

const dateInfer = {
  id: 'date-infer',
  apply(payload) {
    for (const field of ['factualBackground', 'legalQuestion']) {
      const v = payload[field] || '';
      if (RELATIVE_RE.test(v)) {
        const today = new Date().toISOString().slice(0, 10);
        return {
          ruleId: 'date-infer', field,
          currentValue: v, proposedValue: v.replace(RELATIVE_RE, m => `${m} (${today})`),
          reason: 'Replace relative date with explicit ISO date for audit clarity',
        };
      }
    }
    return null;
  },
};

export const RULES = [subjectTrim, titleCaseFix, dateInfer];

export function computeSuggestions(payload) {
  const out = [];
  for (const rule of RULES) {
    const s = rule.apply(payload);
    if (s) out.push(s);
  }
  return out;
}

export function attachAutoCorrect(store) {
  store.subscribe('draft', () => {
    const suggestions = computeSuggestions(store.draft.rlsPayload);
    store.update('ui', u => { u.autocorrectSuggestions = suggestions; });
  });
}
