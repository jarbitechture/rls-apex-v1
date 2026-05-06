// api.mjs — backend API regression suite.
// Each test corresponds to a bug we actually hit during build, not aspirational
// coverage. Pattern from ai-regression-testing skill: "tests for bugs found".
//
// Run: npm run regress           (against http://127.0.0.1:8090 by default)
//      RLS_BASE=http://...  npm run regress
//
// Uses native fetch (Node 18+). No Playwright needed; these are HTTP-only.

const BASE = process.env.RLS_BASE || "http://127.0.0.1:8090";

const RESET = "\x1b[0m";
const GREEN = "\x1b[32m";
const RED   = "\x1b[31m";
const DIM   = "\x1b[2m";

let pass = 0, fail = 0;
const failures = [];

function ok(msg) { pass++; console.log(`  ${GREEN}✓${RESET} ${msg}`); }
function bad(msg, detail) { fail++; failures.push({ msg, detail }); console.log(`  ${RED}✗${RESET} ${msg}\n    ${DIM}${detail}${RESET}`); }

async function expect(name, fn) {
  try { await fn(); ok(name); } catch (e) { bad(name, e.message); }
}

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

async function get(path) {
  const r = await fetch(BASE + path);
  if (!r.ok) throw new Error(`${path} → ${r.status} ${r.statusText}`);
  return r.json();
}
async function post(path, body) {
  const r = await fetch(BASE + path, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!r.ok) throw new Error(`${path} → ${r.status} ${r.statusText}`);
  return r.json();
}

async function streamSSE(path, body) {
  const r = await fetch(BASE + path, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${path} → ${r.status} ${r.statusText}`);
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  const events = [];
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let nl;
    while ((nl = buf.indexOf("\n\n")) !== -1) {
      const chunk = buf.slice(0, nl); buf = buf.slice(nl + 2);
      const lines = chunk.split("\n");
      let evt = "message", data = "";
      for (const l of lines) {
        if (l.startsWith("event:")) evt = l.slice(6).trim();
        else if (l.startsWith("data:")) data = l.slice(5).trim();
      }
      if (data) {
        try { events.push({ event: evt, data: JSON.parse(data) }); } catch {}
      }
    }
  }
  return events;
}

// ─── Tests ────────────────────────────────────────────────────────

async function run() {
  console.log(`API regressions · ${BASE}`);
  console.log("─".repeat(72));

  // BUG-R1: /healthz contract (corpus block landed missing once, was added defensively)
  await expect("/healthz includes corpus.loaded/docs/chunks", async () => {
    const r = await get("/healthz");
    assert(r.ok === true, "ok must be true");
    assert(r.corpus, "corpus block missing");
    assert(typeof r.corpus.loaded === "boolean", "corpus.loaded must be boolean");
    assert(typeof r.corpus.docs === "number", "corpus.docs must be number");
    assert(typeof r.corpus.chunks === "number", "corpus.chunks must be number");
  });

  // BUG-R2: ambient OPENAI_API_KEY auto-activated openai (now defaults to mock)
  await expect("/api/health/llm defaults to mock when LLM_PROVIDER unset", async () => {
    const r = await get("/api/health/llm");
    if (process.env.LLM_PROVIDER && process.env.LLM_PROVIDER !== "mock") {
      console.log(`    ${DIM}(skipping — LLM_PROVIDER=${process.env.LLM_PROVIDER})${RESET}`);
      return;
    }
    assert(r.provider === "mock", `expected provider=mock, got ${r.provider}`);
    assert(r.active === false, `expected active=false, got ${r.active}`);
  });

  // BUG-R3: corpus path was resolving to apps/ after flatten (parents[2] vs [3])
  await expect("/api/corpus loads from project root, not apps/", async () => {
    const r = await get("/api/corpus");
    assert(r.loaded === true, "corpus must load");
    assert(r.documents.length > 0, "must have ingested documents");
  });

  // BUG-R4: each ingested doc must carry source_kind + classification + hash
  await expect("/api/corpus document records carry the full manifest shape", async () => {
    const r = await get("/api/corpus");
    const required = ["id", "source", "source_kind", "classification", "pages", "chunks", "bytes", "hash"];
    for (const d of r.documents) {
      for (const k of required) {
        assert(k in d, `doc ${d.id || '?'} missing field "${k}"`);
      }
      assert(d.hash.startsWith("sha256:"), `doc ${d.id} hash format`);
    }
  });

  // BUG-R5: /api/retrieve Citation shape (id, source, source_kind, pinpoint, excerpt, score)
  await expect("/api/retrieve returns Citation-shaped items", async () => {
    const r = await post("/api/retrieve", { q: "RLS submission", k: 3 });
    assert(Array.isArray(r.items), "items must be array");
    if (r.items.length === 0) throw new Error("expected ≥1 hit for 'RLS submission' on a populated corpus");
    for (const c of r.items) {
      for (const k of ["id", "source", "source_kind", "pinpoint", "excerpt", "score"]) {
        assert(k in c, `citation missing "${k}"`);
      }
      assert(typeof c.score === "number", "score must be numeric");
    }
  });

  // BUG-R6: classification_filter actually filters
  await expect("/api/retrieve classification_filter excludes internal docs", async () => {
    const r = await post("/api/retrieve", {
      q: "RLS submission",
      k: 8,
      classification_filter: ["public_record"],
    });
    const corpus = await get("/api/corpus");
    const internal_ids = new Set(corpus.documents.filter(d => d.classification === "internal").map(d => d.id));
    for (const c of r.items) {
      const doc_id = c.id.split(":")[0];
      assert(!internal_ids.has(doc_id), `internal doc ${doc_id} leaked through public_record filter`);
    }
  });

  // BUG-R7: /api/query SSE done payload now carries citations_source + llm_provider
  await expect("/api/query done payload carries citations_source + llm_provider", async () => {
    const events = await streamSSE("/api/query", { q: "BIE worksheet posting" });
    const done = events.findLast(e => e.event === "done");
    assert(done, "no done event emitted");
    assert(["corpus", "canned", "none"].includes(done.data.citations_source),
           `citations_source invalid: ${done.data.citations_source}`);
    assert(typeof done.data.llm_provider === "string", "llm_provider missing");
  });

  // BUG-R8: /api/query streams ≥1 token event (compose step regression — the
  // 'decide' kind originally had no compose, so panel stayed empty)
  await expect("/api/query streams ≥1 token event", async () => {
    const events = await streamSSE("/api/query", { q: "sole-source procurement" });
    const tokens = events.filter(e => e.event === "token");
    assert(tokens.length > 0, `no token events (got ${events.length} total events)`);
  });

  // BUG-R9: every agent kind streams tokens (originally only precedent/draft/triage
  // composed; decide/summarize/completeness fired SSE but never streamed text)
  for (const kind of ["triage", "precedent", "decide", "draft", "summarize", "completeness"]) {
    await expect(`/api/agent/dispatch[${kind}] streams tokens AND emits done`, async () => {
      const events = await streamSSE("/api/agent/dispatch",
        { kind, context: { q: "sole-source vendor", rls_id: "RLS-26-0141", decision: "accept" } });
      const tokens = events.filter(e => e.event === "token");
      const done = events.findLast(e => e.event === "done");
      assert(tokens.length > 0, `no tokens for kind=${kind}`);
      assert(done, `no done event for kind=${kind}`);
      assert(done.data.kind === kind, `done.kind mismatch`);
    });
  }

  // BUG-R10: every agent kind retrieves citations on every engagement (was only
  // precedent/draft/triage)
  await expect("/api/agent/dispatch[decide] retrieves real citations", async () => {
    const events = await streamSSE("/api/agent/dispatch",
      { kind: "decide", context: { q: "BIE posting requirement", rls_id: "RLS-26-0141", decision: "accept" } });
    const citations = events.filter(e => e.event === "citation");
    assert(citations.length > 0, "decide kind must emit citations from corpus");
    const real = citations.filter(c => /\.(pdf|csv)$/i.test(c.data.source || ""));
    assert(real.length > 0, "expected real corpus citations, got only canned");
  });

  // BUG-R11: /api/feedback writes JSONL and /recent reflects it
  await expect("/api/feedback POST then /recent shows the entry", async () => {
    const lineage = `ln-test-${Date.now()}`;
    await post("/api/feedback",
      { decision: "accept", question: "regression test", lineage_id: lineage });
    const r = await get("/api/feedback/recent");
    const found = r.items.find(i => i.lineage_id === lineage);
    assert(found, "recent feedback did not include the just-posted decision");
    assert(found.decision === "accept", "decision field mangled");
  });

  // BUG-R12: /api/corpus/reload reflects current disk state (stale cache regression)
  await expect("/api/corpus/reload returns the current manifest", async () => {
    const r = await post("/api/corpus/reload");
    assert(r.reloaded === true, "reloaded flag must be true");
    assert(r.total_chunks > 0, "must have chunks after reload");
  });

  // BUG-R13: lens routes return distinct content (LU vs PR same-page bug)
  await expect("/api/rls without filter, vs ?team=Land Use, vs ?type=Public Records — distinct", async () => {
    const all = await get("/api/rls");
    const lu  = await get("/api/rls?team=Land Use");
    const pr  = await get("/api/rls?type=Public Records");
    assert(lu.total > 0 && pr.total > 0, "both filters must hit");
    assert(lu.total !== pr.total, "LU and PR same total — filters not distinct");
    assert(lu.total <= all.total && pr.total <= all.total, "filters can't return more than unfiltered");
  });

  console.log("─".repeat(72));
  console.log(`${pass} pass · ${fail} fail`);
  if (fail > 0) {
    console.log("\nFailures:");
    for (const f of failures) console.log(`  ${RED}✗${RESET} ${f.msg}: ${f.detail}`);
    process.exit(1);
  }
}

run().catch(e => { console.error(`harness error: ${e}`); process.exit(2); });
