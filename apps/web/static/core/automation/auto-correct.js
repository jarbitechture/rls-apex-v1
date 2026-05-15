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

// L14 — policy-lint LLM rule. Calls POST /api/lint/policy. Gating per
// v0.2.0b smart-surface contract: blurredFields + dedup + max 1 chip per field.

function _defaultHash(value) {
  // 32-bit FNV-1a — sufficient for dismiss dedup, no crypto requirement
  let h = 0x811c9dc5;
  for (let i = 0; i < value.length; i++) {
    h ^= value.charCodeAt(i);
    h = (h * 0x01000193) >>> 0;
  }
  return h.toString(16);
}

const policyLintLlm = {
  id: 'policy-lint-llm',
  async: true,
  async apply(payload, options = {}) {
    const ui = payload.ui || {};
    const bf = ui.blurredFields;
    // Gate: rule only fires for fields the user has blurred (touched + moved away)
    // blurredFields may be a Set (production store shape) or an Array (test fixtures)
    const isBlurred = (f) => bf instanceof Set ? bf.has(f) : Array.isArray(bf) ? bf.includes(f) : false;
    const target = isBlurred('factualBackground') ? 'factualBackground'
                 : isBlurred('legalQuestion') ? 'legalQuestion' : null;
    if (!target) return null;

    let resp;
    try {
      resp = await fetch('/api/lint/policy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rlsPayload: payload }),
      });
    } catch (e) {
      return null;
    }
    if (!resp.ok) return null;

    let data;
    try {
      data = await resp.json();
    } catch (e) {
      return null;
    }
    const suggestions = data.suggestions || [];
    if (suggestions.length === 0) return [];

    // Dismiss-dedup: drop suggestions whose (ruleId, field, value-hash) tuple
    // is in ui.dismissedSuggestions
    const dismissed = new Set(ui.dismissedSuggestions || []);
    const computeHash = options.computeHash || _defaultHash;
    return suggestions.filter((s) => {
      const value = payload[s.field] || '';
      const tuple = `${s.ruleId}:${s.field}:${computeHash(value)}`;
      return !dismissed.has(tuple);
    });
  },
};

export const RULES = [subjectTrim, titleCaseFix, dateInfer, policyLintLlm];

export function computeSuggestions(payload) {
  const out = [];
  for (const rule of RULES) {
    // Skip async rules — they are handled by computeAsyncSuggestions
    if (rule.async) continue;
    const s = rule.apply(payload);
    if (s) out.push(s);
  }
  return out;
}

export async function computeAsyncSuggestions(payload, options = {}) {
  const out = [];
  for (const rule of RULES.filter(r => r.async)) {
    try {
      const result = await rule.apply(payload, options);
      if (Array.isArray(result)) {
        out.push(...result);
      } else if (result) {
        out.push(result);
      }
    } catch (e) {
      // Swallow errors — async suggestions are advisory, never blocking
    }
  }
  return out;
}

export function attachAutoCorrect(store) {
  store.subscribe('draft', () => {
    // Synchronous rules — update immediately
    const suggestions = computeSuggestions(store.draft.rlsPayload);
    store.update('ui', u => { u.autocorrectSuggestions = suggestions; });

    // Async rules — fire-and-forget, merge results when they resolve
    // Forward only blurredFields so the gate in policyLintLlm fires in production
    computeAsyncSuggestions({ ...store.draft.rlsPayload, ui: { blurredFields: store.ui.blurredFields } }).then(asyncSuggestions => {
      if (asyncSuggestions.length > 0) {
        store.update('ui', u => {
          u.autocorrectSuggestions = (u.autocorrectSuggestions || []).concat(asyncSuggestions);
        });
      }
    }).catch(() => {
      // Errors swallowed — telemetry never blocks the user-facing action
    });
  });
}
