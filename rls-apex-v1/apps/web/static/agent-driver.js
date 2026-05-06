// agent-driver.js — global click-delegate that turns every action button
// into an agent dispatch. Loaded after rls-api.js. Adds a floating
// AI Co-pilot panel (bottom-right) that streams responses for every
// qualifying click. Non-invasive — React state continues to work; the
// agent panel runs alongside.
//
// Routing heuristic:
//   "Submit" / "Send" / "New RLS" / "Create"  -> triage
//   "Accept" / "Approve" / "Acknowledge"      -> decide(accept)
//   "Reject" / "Deny"                         -> decide(reject)
//   "Return" / "Send back" / "Revise"         -> decide(return)
//   "Search" / "Find precedents"              -> precedent
//   "Draft" / "Compose" / "Generate"          -> draft
//   "Score" / "Check completeness"            -> completeness
//   "Summarize" / "TL;DR"                     -> summarize
//
// Skips sidebar nav buttons (Dashboard, Submissions, etc.), tweak-panel
// controls, and any element with [data-no-agent] or .no-agent.

(function () {
  if (window.__RLS_AGENT_DRIVER_LOADED__) return;
  window.__RLS_AGENT_DRIVER_LOADED__ = true;

  const NAV_LABELS = new Set([
    'dashboard', 'submissions', 'inbox', 'drafts', 'ai co-pilot', 'ai',
    'code enforcement', 'bie worksheets', 'land use & planning', 'public records',
    'ai co-pilot', 'policy graph', 'precedents', 'kpi analytics',
    'breaching sla', 'awaiting acknowledgm', 'my team', 'all',
    'jump to page', 'tweaks', 'cancel', 'back', 'next', 'previous', 'close',
    'edit', 'view', 'open',
  ]);

  const ROUTES = [
    { test: /\bnew rls\b|\bnew submission\b|\bcreate\b|\bstart\b/i,            kind: 'triage', tone: 'New submission' },
    { test: /\b(submit|send for review)\b/i,                                    kind: 'triage', tone: 'Submitting' },
    { test: /\b(accept|approve|acknowledge|✓ accept)\b/i,                       kind: 'decide', extra: { decision: 'accept' } },
    { test: /\b(reject|deny|✗ reject)\b/i,                                      kind: 'decide', extra: { decision: 'reject' } },
    { test: /\b(return|send back|revise|request revision)\b/i,                  kind: 'decide', extra: { decision: 'return' } },
    { test: /\b(find precedents?|search precedents?|precedent search)\b/i,      kind: 'precedent' },
    { test: /\b(draft|compose|generate response|write reply)\b/i,               kind: 'draft' },
    { test: /\b(score|check completeness|completeness)\b/i,                     kind: 'completeness' },
    { test: /\b(summari[sz]e|tl;dr|key points)\b/i,                              kind: 'summarize' },
    { test: /\b(ask|run|go)\b/i,                                                kind: 'precedent' }, // generic ask
  ];

  // ─── Panel ──────────────────────────────────────────────────────
  const panelHTML = `
<div id="rls-agent-panel" hidden>
  <div class="rls-agent-head">
    <span class="rls-agent-dot"></span>
    <span class="rls-agent-title">AI Co-pilot</span>
    <span class="rls-agent-kind"></span>
    <button class="rls-agent-min" title="Minimize">_</button>
    <button class="rls-agent-close" title="Hide">×</button>
  </div>
  <div class="rls-agent-trace"></div>
  <div class="rls-agent-body">
    <div class="rls-agent-empty">No activity yet. Click <b>Accept</b>, <b>Reject</b>, <b>Submit</b>, or <b>Find precedents</b> on any submission.</div>
  </div>
</div>`;

  const css = `
#rls-agent-panel {
  position: fixed; right: 18px; bottom: 18px; width: 380px; max-height: 65vh;
  background: #ffffff; border: 1px solid #e6e5e1; border-radius: 12px;
  box-shadow: 0 14px 36px rgba(0,0,0,0.10), 0 2px 8px rgba(0,0,0,0.05);
  font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", sans-serif;
  font-size: 13px; color: #1A1A1A; z-index: 9999;
  display: flex; flex-direction: column; overflow: hidden;
}
#rls-agent-panel.minimized { max-height: 36px; }
#rls-agent-panel.minimized .rls-agent-trace,
#rls-agent-panel.minimized .rls-agent-body { display: none; }
.rls-agent-head {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; background: #FAFAF9; border-bottom: 1px solid #e6e5e1;
}
.rls-agent-dot { width: 8px; height: 8px; border-radius: 50%; background: #2c7d4a; flex: 0 0 auto; }
.rls-agent-dot.busy { background: #2B7A9E; animation: rls-blink 0.8s ease-in-out infinite; }
@keyframes rls-blink { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }
.rls-agent-title { font-weight: 600; font-size: 12px; }
.rls-agent-kind { color: #80807B; font-size: 11px; font-family: ui-monospace, monospace; margin-left: 4px; flex: 1; }
.rls-agent-min, .rls-agent-close {
  background: transparent; border: 0; color: #80807B; font-size: 14px;
  cursor: pointer; padding: 0 4px; line-height: 1;
}
.rls-agent-min:hover, .rls-agent-close:hover { color: #1A1A1A; }
.rls-agent-trace {
  display: flex; gap: 4px; flex-wrap: wrap;
  padding: 8px 12px; border-bottom: 1px dashed #e6e5e1;
}
.rls-agent-trace:empty { display: none; }
.rls-agent-step {
  background: #ffffff; border: 1px solid #e6e5e1;
  padding: 2px 8px; border-radius: 999px; font-size: 10px; color: #80807B;
  display: inline-flex; align-items: center; gap: 4px;
  font-family: ui-monospace, monospace;
}
.rls-agent-step.active { border-color: #2B7A9E; color: #2B7A9E; }
.rls-agent-step.done   { border-color: #1F8A4C; color: #1F8A4C; }
.rls-agent-step .sdot { width: 5px; height: 5px; border-radius: 50%; background: #B5B4AE; }
.rls-agent-step.active .sdot { background: #2B7A9E; animation: rls-blink 0.8s ease-in-out infinite; }
.rls-agent-step.done .sdot   { background: #1F8A4C; }
.rls-agent-body {
  padding: 12px; overflow-y: auto; flex: 1; min-height: 60px;
}
.rls-agent-body .rls-agent-empty { color: #80807B; font-style: italic; font-size: 12px; }
.rls-agent-answer {
  white-space: pre-wrap; line-height: 1.55; margin: 0 0 10px;
  font-size: 13px;
}
.rls-agent-cite {
  background: #FAFAF9; border: 1px solid #e6e5e1; border-radius: 6px;
  padding: 8px 10px; margin-top: 6px;
}
.rls-agent-cite .id { font-family: ui-monospace, monospace; font-size: 11px; color: #2B7A9E; font-weight: 600; }
.rls-agent-cite .meta { color: #80807B; font-size: 10px; margin-left: 6px; }
.rls-agent-cite .ex { font-size: 12px; margin-top: 4px; line-height: 1.5; color: #4A4A47; }
.rls-agent-meta {
  margin-top: 8px; color: #80807B; font-size: 10px;
  font-family: ui-monospace, monospace; display: flex; gap: 12px; flex-wrap: wrap;
}
.rls-agent-toast {
  position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
  background: #1A1A1A; color: white; padding: 8px 16px; border-radius: 6px;
  font-size: 12px; opacity: 0; transition: opacity 0.18s; pointer-events: none;
  z-index: 10000;
}
.rls-agent-toast.show { opacity: 1; }
`;

  function ensurePanel() {
    if (document.getElementById('rls-agent-panel')) return;
    const style = document.createElement('style');
    style.textContent = css;
    document.head.appendChild(style);
    const wrap = document.createElement('div');
    wrap.innerHTML = panelHTML;
    document.body.appendChild(wrap.firstElementChild);

    const toast = document.createElement('div');
    toast.className = 'rls-agent-toast';
    toast.id = 'rls-agent-toast';
    document.body.appendChild(toast);

    const panel = document.getElementById('rls-agent-panel');
    panel.querySelector('.rls-agent-min').onclick   = () => panel.classList.toggle('minimized');
    panel.querySelector('.rls-agent-close').onclick = () => { panel.hidden = true; };
  }

  function showToast(msg) {
    const t = document.getElementById('rls-agent-toast');
    if (!t) return;
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => t.classList.remove('show'), 1700);
  }

  function setBusy(busy, kindLabel) {
    const p = document.getElementById('rls-agent-panel');
    p.hidden = false;
    p.classList.remove('minimized');
    p.querySelector('.rls-agent-dot').classList.toggle('busy', !!busy);
    p.querySelector('.rls-agent-kind').textContent = kindLabel || '';
  }

  function resetTrace() {
    const t = document.querySelector('#rls-agent-panel .rls-agent-trace');
    t.innerHTML = '';
  }

  function setStep(name, status, ms) {
    if (name === '_chain') return;
    const trace = document.querySelector('#rls-agent-panel .rls-agent-trace');
    let el = trace.querySelector(`[data-name="${CSS.escape(name)}"]`);
    if (!el) {
      el = document.createElement('span');
      el.className = 'rls-agent-step';
      el.dataset.name = name;
      el.innerHTML = `<span class="sdot"></span><span class="lab">${name}</span><span class="ms"></span>`;
      trace.appendChild(el);
    }
    el.classList.remove('active', 'done');
    if (status === 'start') el.classList.add('active');
    if (status === 'done') {
      el.classList.add('done');
      if (ms != null) el.querySelector('.ms').textContent = ` ${ms}ms`;
    }
  }

  function startBody() {
    const b = document.querySelector('#rls-agent-panel .rls-agent-body');
    b.innerHTML = '<div class="rls-agent-answer"></div>';
    return b.querySelector('.rls-agent-answer');
  }

  function appendCitation(c) {
    const b = document.querySelector('#rls-agent-panel .rls-agent-body');
    const div = document.createElement('div');
    div.className = 'rls-agent-cite';
    div.innerHTML = `<div><span class="id">${c.id}</span><span class="meta">${c.source_kind} · ${c.pinpoint}</span></div><div class="ex">${c.excerpt}</div>`;
    b.appendChild(div);
  }

  function appendMeta(payload) {
    const b = document.querySelector('#rls-agent-panel .rls-agent-body');
    const div = document.createElement('div');
    div.className = 'rls-agent-meta';
    const parts = [];
    if (payload.intent)        parts.push(`intent=${payload.intent}`);
    if (payload.lineage_id)    parts.push(payload.lineage_id);
    if (payload.duration_ms != null) parts.push(`${payload.duration_ms}ms`);
    if (payload.prompt_tokens != null && payload.output_tokens != null)
      parts.push(`${payload.prompt_tokens} in · ${payload.output_tokens} out`);
    div.textContent = parts.join(' · ');
    b.appendChild(div);
  }

  // ─── Routing ────────────────────────────────────────────────────

  function pickRoute(button) {
    if (button.dataset.noAgent !== undefined) return null;
    if (button.classList.contains('no-agent')) return null;

    const text = (button.textContent || button.getAttribute('aria-label') || '').trim().toLowerCase();
    if (!text || text.length > 40) return null;
    if (NAV_LABELS.has(text)) return null;

    for (const r of ROUTES) if (r.test.test(text)) return { ...r, text };
    return null;
  }

  function findRlsContext(button) {
    // Walk up looking for data-rls-id, or scrape sibling text for an RLS-XX-XXXX id.
    let n = button;
    while (n && n !== document.body) {
      if (n.dataset && n.dataset.rlsId) return n.dataset.rlsId;
      n = n.parentElement;
    }
    const m = (button.closest('[role="row"], [class*="row"], li, article, section, .card, .detail') || document.body).textContent.match(/RLS-\d{2}-\d{4}/);
    return m ? m[0] : null;
  }

  // ─── Dispatch ───────────────────────────────────────────────────

  let inflight = false;

  async function dispatch(route, button) {
    if (inflight) return;
    inflight = true;
    ensurePanel();
    setBusy(true, route.kind);
    resetTrace();
    const answerEl = startBody();
    const stepStarts = {};
    const rls_id = findRlsContext(button);
    const ctx = {
      rls_id,
      title: (button.closest('[data-rls-title], [class*="title"], h1, h2, h3') || {}).textContent || undefined,
      ...((route.extra || {})),
    };
    if (route.kind === 'decide' && rls_id) ctx.new_status = ctx.decision === 'accept' ? 'Acknowledged' : ctx.decision === 'reject' ? 'Rejected' : 'Submitted';

    showToast(`Agent · ${route.kind}${rls_id ? ' · ' + rls_id : ''}`);

    try {
      // Side-effects first (so the activity log/state actually changes), then stream the agent narrative.
      if (route.kind === 'decide' && rls_id) {
        try { await window.RLS_API.rls.decide(rls_id, ctx.decision); } catch (e) { /* mock missing — keep going */ }
      }
      await window.RLS_API.stream('/api/agent/dispatch', { kind: route.kind, context: ctx }, ({ event, data }) => {
        if (event === 'agent') {
          document.querySelector('#rls-agent-panel .rls-agent-kind').textContent = `${data.kind} · ${data.lineage_id}`;
        } else if (event === 'step') {
          if (data.status === 'start') stepStarts[data.name] = data.t_ms;
          const ms = (data.status === 'done' && stepStarts[data.name] != null) ? (data.t_ms - stepStarts[data.name]) : null;
          setStep(data.name, data.status, ms);
        } else if (event === 'token') {
          answerEl.appendChild(document.createTextNode(data.text));
        } else if (event === 'citation') {
          appendCitation(data);
        } else if (event === 'done') {
          appendMeta(data);
        }
      });
    } catch (e) {
      const b = document.querySelector('#rls-agent-panel .rls-agent-body');
      b.innerHTML = `<div class="rls-agent-empty">Agent error: ${e.message}</div>`;
    } finally {
      setBusy(false);
      inflight = false;
    }
  }

  // ─── Click delegate ─────────────────────────────────────────────

  document.addEventListener('click', (ev) => {
    const t = ev.target;
    const btn = t.closest('button, a[role="button"]');
    if (!btn) return;
    if (btn.closest('#rls-agent-panel')) return;       // ignore panel's own controls
    const route = pickRoute(btn);
    if (!route) return;
    // Don't preventDefault — let React do its thing; agent runs alongside.
    dispatch(route, btn);
  }, true);

  // Auto-show panel after a moment so the user sees it exists.
  window.addEventListener('load', () => {
    setTimeout(() => { ensurePanel(); document.getElementById('rls-agent-panel').hidden = false; }, 600);
  });
})();
