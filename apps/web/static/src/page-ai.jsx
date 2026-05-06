// Validate — single-purpose pre-submission check. Paste a draft RLS,
// the gateway streams a step trace + answer + citations from the corpus.
// No fake chat history, no agent picker, no pre-baked turns.
//
// The classic chat surface (with PolicyMatcher / PrecedentRetriever / etc.
// agent chips and the conversational thread) lived here previously and
// was kept off the main path because the pilot's actual user task is one
// thing: validate a draft before submission. If you need the rich agent
// view, navigate to Dashboard for the power view.

const { I, UI } = window;
const { Pill, Btn, Card } = UI;
const { PageHeader } = window;

const STEP_LABEL = {
  classify: "classify",
  "retrieve.hybrid": "retrieve",
  "policy_graph.cited_by": "graph",
  rank: "rank",
  compose: "compose",
};

function StepRibbon({ steps }) {
  if (!steps || !steps.length) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6, margin: "16px 0 12px" }}>
      {steps.map(s => {
        const color = s.status === "done" ? "var(--success)" : "var(--primary)";
        const dotPulse = s.status === "active";
        return (
          <span key={s.name} style={{
            display: "inline-flex", alignItems: "center", gap: 5,
            border: `1px solid ${color}`, color,
            background: "var(--canvas)",
            padding: "2px 9px", borderRadius: 999,
            fontSize: 11, fontFamily: "var(--mono)",
          }}>
            <span style={{
              width: 6, height: 6, borderRadius: 3, background: color,
              animation: dotPulse ? "pulse 0.9s ease-in-out infinite" : "none",
            }} />
            {STEP_LABEL[s.name] || s.name}
            {s.duration_ms != null && <span style={{ color: "var(--ink-3)" }}>· {s.duration_ms}ms</span>}
          </span>
        );
      })}
    </div>
  );
}

function CitationCard({ c }) {
  return (
    <div style={{
      background: "var(--canvas)", border: "1px solid var(--border)",
      borderRadius: 8, padding: "10px 14px", marginTop: 8,
    }}>
      <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
        <span className="mono" style={{ fontSize: 12, color: "var(--primary)", fontWeight: 600 }}>{c.id}</span>
        <span className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)" }}>{c.source_kind} · {c.pinpoint}</span>
      </div>
      <div style={{ fontSize: 13, color: "var(--ink-2)", marginTop: 5, lineHeight: 1.55 }}>{c.excerpt}</div>
    </div>
  );
}

const SAMPLE_DRAFTS = [
  "Can the County contract a sole-source IT vendor under §125.65 if findings are drafted concurrently?",
  "Is a 60-month evergreen renewal enforceable against the County?",
  "Vested rights claim under prior LDC §6.4.A.5 for a setback variance — is this defensible?",
  "Can we exempt these civil-litigation records under §119.071(2)(d)?",
];

const AiPage = ({ go }) => {
  const [draft, setDraft] = React.useState("");
  const [validating, setValidating] = React.useState(false);
  const [steps, setSteps] = React.useState([]);
  const [answer, setAnswer] = React.useState("");
  const [citations, setCitations] = React.useState([]);
  const [done, setDone] = React.useState(null);
  const [error, setError] = React.useState(null);
  const [decision, setDecision] = React.useState(null);

  const stepTimings = React.useRef({});

  async function handleValidate() {
    const q = draft.trim();
    if (!q || validating) return;
    setValidating(true);
    setSteps([]); setAnswer(""); setCitations([]);
    setDone(null); setError(null); setDecision(null);
    stepTimings.current = {};

    try {
      await window.RLS_API.stream("/api/query", { q }, ({ event, data }) => {
        if (event === "step") {
          if (data.name === "_chain") return;
          if (data.status === "start") {
            stepTimings.current[data.name] = data.t_ms;
            setSteps(prev => [...prev.filter(s => s.name !== data.name), { name: data.name, status: "active" }]);
          } else if (data.status === "done") {
            const start = stepTimings.current[data.name] ?? 0;
            const ms = (data.t_ms != null) ? data.t_ms - start : null;
            setSteps(prev => [...prev.filter(s => s.name !== data.name), { name: data.name, status: "done", duration_ms: ms }]);
          }
        } else if (event === "token") {
          setAnswer(prev => prev + data.text);
        } else if (event === "citation") {
          setCitations(prev => [...prev, data]);
        } else if (event === "done") {
          setDone(data);
        }
      });
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setValidating(false);
    }
  }

  async function handleDecision(d) {
    if (!done) return;
    try {
      await window.RLS_API.feedback.send(d, {
        question: draft,
        intent: done.intent,
        lineage_id: done.lineage_id,
      });
      setDecision(d);
    } catch (e) {
      setError(`feedback failed: ${e.message || e}`);
    }
  }

  function reset() {
    setDraft(""); setSteps([]); setAnswer(""); setCitations([]);
    setDone(null); setError(null); setDecision(null);
  }

  const hasResult = answer.length > 0 || citations.length > 0 || done;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <PageHeader
        title="Validate"
        sub="Paste a draft RLS — the gateway grades it against the County Attorney corpus and returns a cure path. Citations are real; the LLM call is mocked until SGLang lands."
      />
      <div style={{ flex: 1, overflow: "auto" }}>
        <div style={{ maxWidth: 760, margin: "0 auto", padding: "28px 24px 80px" }}>

          {/* Input section */}
          <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: "var(--ink-2)", marginBottom: 6 }}>
            DRAFT RLS
          </label>
          <textarea
            value={draft}
            onChange={e => setDraft(e.target.value)}
            placeholder="Paste the legal question and supporting facts. Plain text is fine."
            disabled={validating}
            style={{
              width: "100%", minHeight: 140, padding: 14,
              background: "var(--canvas)", border: "1px solid var(--border)", borderRadius: 8,
              fontFamily: "var(--sans)", fontSize: 14, lineHeight: 1.55, color: "var(--ink)",
              resize: "vertical", boxSizing: "border-box",
            }}
            onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") handleValidate(); }}
          />

          {!hasResult && !validating && (
            <div style={{ marginTop: 10, display: "flex", gap: 6, flexWrap: "wrap" }}>
              {SAMPLE_DRAFTS.map(s => (
                <button key={s} onClick={() => setDraft(s)} style={{
                  border: "1px solid var(--border)", background: "var(--canvas)",
                  padding: "4px 10px", borderRadius: 999, fontSize: 11.5,
                  color: "var(--ink-2)", cursor: "pointer",
                }}>{s.length > 64 ? s.slice(0, 61) + "…" : s}</button>
              ))}
            </div>
          )}

          <div style={{ marginTop: 14, display: "flex", gap: 10, alignItems: "center" }}>
            <Btn variant="primary" onClick={handleValidate} disabled={!draft.trim() || validating} icon={<I.Bolt size={13} />}>
              {validating ? "Validating…" : "Validate"}
            </Btn>
            {(hasResult || draft) && (
              <Btn variant="ghost" onClick={reset}>Clear</Btn>
            )}
            <span style={{ marginLeft: "auto", color: "var(--ink-3)", fontSize: 11, fontFamily: "var(--mono)" }}>
              POST /api/query · SSE · ⌘⏎ submits
            </span>
          </div>

          {error && (
            <div style={{ marginTop: 16, padding: 12, background: "color-mix(in oklab, var(--destructive) 10%, white)", border: "1px solid var(--destructive)", borderRadius: 8, fontSize: 13, color: "var(--destructive)" }}>
              {error}
            </div>
          )}

          {/* Result section */}
          {hasResult && <StepRibbon steps={steps} />}

          {hasResult && (
            <div style={{ marginTop: 8, padding: 18, background: "var(--canvas)", border: "1px solid var(--border)", borderRadius: 8, lineHeight: 1.65, fontSize: 14, color: "var(--ink-1)", whiteSpace: "pre-wrap" }}>
              {answer || (validating ? <span style={{ color: "var(--ink-3)" }}>…</span> : null)}
            </div>
          )}

          {citations.length > 0 && (
            <>
              <div style={{ marginTop: 18, fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.06, color: "var(--ink-3)" }}>Citations</div>
              <div>{citations.map((c, i) => <CitationCard key={c.id || i} c={c} />)}</div>
            </>
          )}

          {done && (
            <div style={{ marginTop: 22, paddingTop: 14, borderTop: "1px solid var(--border)", display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <Btn variant="default" onClick={() => handleDecision("accept")} disabled={!!decision}
                   style={decision === "accept" ? { background: "var(--success)", color: "white" } : {}}
                   icon={<I.Check size={13} />}>
                {decision === "accept" ? "Accepted" : "Accept"}
              </Btn>
              <Btn variant="default" onClick={() => handleDecision("reject")} disabled={!!decision}
                   style={decision === "reject" ? { background: "var(--destructive)", color: "white" } : {}}>
                {decision === "reject" ? "Rejected" : "Reject"}
              </Btn>
              <Btn variant="default" onClick={() => handleDecision("return")} disabled={!!decision}
                   style={decision === "return" ? { background: "var(--warning)", color: "white" } : {}}>
                {decision === "return" ? "Returned" : "Return for revision"}
              </Btn>
              <span style={{ marginLeft: "auto", color: "var(--ink-3)", fontSize: 11, fontFamily: "var(--mono)" }}>
                {done.prompt_tokens} in · {done.output_tokens} out · {done.lineage_id} · {done.citations_source}
              </span>
            </div>
          )}
        </div>
      </div>
      <style>{`@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.35; } }`}</style>
    </div>
  );
};

window.AiPage = AiPage;
