// rls-api.js — gateway client. Lives at /rls-api.js, loaded by every page.
// Production-shaped contract: in DEV_MODE the gateway returns mock data
// matching window.SAMPLE shapes. When SGLang lands the call sites stay the same.
//
// Usage from any React page:
//   const data = await window.RLS_API.get('/api/rls')
//   await window.RLS_API.post('/api/rls/RLS-26-0141/decision', { decision: 'accept' })
//   const stream = await window.RLS_API.stream('/api/query', { q: 'sole-source...' }, onEvent)

(function (global) {
  const base = '';

  async function request(path, opts = {}) {
    const headers = Object.assign({ 'Content-Type': 'application/json' }, opts.headers || {});
    const res = await fetch(base + path, {
      method: opts.method || 'GET',
      headers,
      body: opts.body != null ? (typeof opts.body === 'string' ? opts.body : JSON.stringify(opts.body)) : undefined,
      credentials: 'same-origin',
    });
    if (!res.ok) {
      const text = await res.text();
      throw Object.assign(new Error(`${res.status} ${res.statusText}`), { status: res.status, body: text });
    }
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) return res.json();
    return res.text();
  }

  async function stream(path, body, onEvent) {
    // SSE consumer for /api/query and similar streaming endpoints.
    // onEvent({ event, data }) is called per parsed frame.
    const res = await fetch(base + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body || {}),
    });
    if (!res.ok) throw Object.assign(new Error(`${res.status}`), { status: res.status });
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let nl;
      while ((nl = buf.indexOf('\n\n')) !== -1) {
        const chunk = buf.slice(0, nl);
        buf = buf.slice(nl + 2);
        const lines = chunk.split('\n');
        let evt = 'message', data = '';
        for (const l of lines) {
          if (l.startsWith('event:')) evt = l.slice(6).trim();
          else if (l.startsWith('data:')) data = l.slice(5).trim();
        }
        if (!data) continue;
        try { onEvent({ event: evt, data: JSON.parse(data) }); }
        catch { onEvent({ event: evt, data }); }
      }
    }
  }

  global.RLS_API = {
    get:  (path)         => request(path),
    post: (path, body)   => request(path, { method: 'POST',   body }),
    put:  (path, body)   => request(path, { method: 'PUT',    body }),
    del:  (path)         => request(path, { method: 'DELETE' }),
    stream,

    // Shorthand methods that match the gateway endpoints. Components can
    // adopt these incrementally; callers that haven't been wired yet keep
    // their inline window.SAMPLE data and the UI never breaks.
    rls: {
      list:    ()                  => request('/api/rls'),
      get:     (id)                => request(`/api/rls/${encodeURIComponent(id)}`),
      draft:   (body)              => request('/api/rls/draft', { method: 'POST', body }),
      decide:  (id, decision, note) => request(`/api/rls/${encodeURIComponent(id)}/decision`,
                                              { method: 'POST', body: { decision, note } }),
    },
    drafts: {
      list:   ()              => request('/api/drafts'),
      create: (body)          => request('/api/drafts', { method: 'POST', body }),
      save:   (id, body)      => request(`/api/drafts/${encodeURIComponent(id)}`, { method: 'PUT', body }),
    },
    precedents: {
      search: (q)             => request(`/api/precedents?q=${encodeURIComponent(q)}`),
    },
    kpi:     ()               => request('/api/kpi/summary'),
    inbox:   ()               => request('/api/inbox'),
    queue:   ()               => request('/api/queue'),
    teams:   ()               => request('/api/team-load'),
    compliance: ()            => request('/api/compliance-pulse'),
    feedback: {
      send:   (decision, ctx) => request('/api/feedback', { method: 'POST', body: { decision, ...ctx } }),
      recent: ()              => request('/api/feedback/recent'),
    },
    health:  ()               => request('/api/health/sidecar'),
  };
})(window);
