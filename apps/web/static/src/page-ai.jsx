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

function ScoreBlock({ score, band, intent }) {
  if (score == null) return null;
  // Liquid-glass-flavored score plate — translucent surface, color tint,
  // layered shadows. Web-native port (no iOS API on web).
  const bandStyle = {
    low:             { tint: "var(--success)",     label: "LOW",              inverted: false },
    medium:          { tint: "var(--warning)",     label: "MEDIUM",           inverted: false },
    high:            { tint: "var(--destructive)", label: "HIGH",             inverted: false },
    likely_rejected: { tint: "var(--destructive)", label: "LIKELY REJECTED",  inverted: true  },
  }[band] || { tint: "var(--ink-2)", label: (band || "—").toUpperCase(), inverted: false };
  const tint = bandStyle.tint;
  const inv = bandStyle.inverted;

  // Inverted (likely_rejected) = solid red surface with white text.
  // Otherwise = translucent tinted glass with tint-colored text.
  const surfaceBg = inv
    ? tint
    : `linear-gradient(135deg, color-mix(in oklab, ${tint} 10%, white), color-mix(in oklab, ${tint} 4%, var(--canvas)))`;
  const fgText = inv ? "white" : tint;
  const ink2 = inv ? "color-mix(in oklab, white 78%, transparent)" : "var(--ink-2)";
  const chipBg = inv ? "color-mix(in oklab, white 18%, transparent)" : tint;
  const chipFg = inv ? "white" : "white";
  const divider = inv ? "color-mix(in oklab, white 30%, transparent)"
                       : `color-mix(in oklab, ${tint} 22%, transparent)`;

  return (
    <div style={{
      marginTop: 22, padding: "18px 20px",
      background: surfaceBg,
      backdropFilter: "blur(18px) saturate(160%)",
      WebkitBackdropFilter: "blur(18px) saturate(160%)",
      border: `1px solid color-mix(in oklab, ${tint} ${inv ? 60 : 30}%, transparent)`,
      borderRadius: 14,
      boxShadow: `
        0 1px 0 color-mix(in oklab, white ${inv ? 30 : 70}%, transparent) inset,
        0 -1px 0 color-mix(in oklab, ${tint} 14%, transparent) inset,
        0 14px 32px -14px color-mix(in oklab, ${tint} 38%, transparent),
        0 2px 8px -2px rgba(0, 0, 0, 0.06)
      `,
      display: "grid", gridTemplateColumns: "auto 1fr auto", alignItems: "center", gap: 16,
    }}>
      <div>
        <div style={{ fontSize: 11, fontWeight: 600, color: fgText, letterSpacing: 0.08, textTransform: "uppercase", opacity: inv ? 0.85 : 1 }}>Rejection probability</div>
        <div className="num" style={{ fontSize: 32, fontWeight: 700, color: fgText, lineHeight: 1.05, marginTop: 4 }}>{score}<span style={{ fontSize: 14, fontWeight: 500, marginLeft: 2, opacity: 0.7 }}>/100</span></div>
      </div>
      <div style={{ paddingLeft: 16, borderLeft: `1px solid ${divider}` }}>
        <div style={{
          display: "inline-block", padding: "3px 11px", borderRadius: 999,
          background: chipBg, color: chipFg, fontSize: 11, fontWeight: 700, letterSpacing: 0.08,
        }}>{bandStyle.label}</div>
        <div style={{ fontSize: 12, color: ink2, marginTop: 7 }}>Classified as <span className="mono" style={{ color: fgText, fontWeight: 600 }}>{intent || "—"}</span></div>
      </div>
    </div>
  );
}

function CurePath({ items, citations }) {
  if (!items || !items.length) return null;
  const cmap = {};
  for (const c of (citations || [])) cmap[c.id] = c;
  return (
    <div style={{ marginTop: 18 }}>
      <div style={{ fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.06, color: "var(--ink-3)", marginBottom: 8 }}>
        Cure path · {items.length} step{items.length === 1 ? "" : "s"}
      </div>
      <ol style={{ margin: 0, padding: 0, listStyle: "none" }}>
        {items.map((it, i) => (
          <li key={i} style={{
            display: "grid", gridTemplateColumns: "28px 1fr", gap: 12,
            padding: "12px 16px", marginTop: i ? 8 : 0,
            // Selective glass — translucent surface, soft inner highlight,
            // primary-tinted shadow that ties to the Score block above.
            background: "linear-gradient(135deg, color-mix(in oklab, var(--primary) 5%, white), var(--canvas))",
            backdropFilter: "blur(14px) saturate(150%)",
            WebkitBackdropFilter: "blur(14px) saturate(150%)",
            border: "1px solid color-mix(in oklab, var(--primary) 18%, transparent)",
            borderRadius: 12,
            boxShadow: `
              0 1px 0 color-mix(in oklab, white 70%, transparent) inset,
              0 8px 20px -10px color-mix(in oklab, var(--primary) 22%, transparent),
              0 1px 3px -1px rgba(0,0,0,0.05)
            `,
          }}>
            <div style={{
              width: 22, height: 22, borderRadius: 11,
              background: "color-mix(in oklab, var(--primary) 14%, white)", color: "var(--primary-ink)",
              fontSize: 11, fontWeight: 700, display: "grid", placeItems: "center",
            }}>{i + 1}</div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: "var(--ink-1)", lineHeight: 1.4 }}>{it.title}</div>
              <div style={{ fontSize: 13, color: "var(--ink-2)", marginTop: 4, lineHeight: 1.55 }}>{it.detail}</div>
              {it.citation_id && (
                <div style={{ marginTop: 6 }}>
                  <span className="mono" style={{ fontSize: 11, color: "var(--primary)", fontWeight: 600 }}>{it.citation_id}</span>
                  {cmap[it.citation_id]?.pinpoint && <span className="mono" style={{ fontSize: 11, color: "var(--ink-3)", marginLeft: 6 }}>· {cmap[it.citation_id].pinpoint}</span>}
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

// Memoized — the parent re-renders on every token; without React.memo each
// citation card would re-render too. Equality on Citation.id is enough since
// the shape is immutable per id.
const CitationCard = React.memo(function CitationCard({ c }) {
  return (
    <div style={{
      background: "var(--canvas)", border: "1px solid var(--border)",
      borderRadius: 8, padding: "10px 14px", marginTop: 8,
    }}>
      <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
        <span className="mono" style={{ fontSize: 12, color: "var(--primary)", fontWeight: 600 }}>{c.id}</span>
        <span className="mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>{c.source_kind} · {c.pinpoint}</span>
      </div>
      <div style={{ fontSize: 13, color: "var(--ink-2)", marginTop: 5, lineHeight: 1.55 }}>{c.excerpt}</div>
    </div>
  );
}, (prev, next) => prev.c.id === next.c.id);

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
                  padding: "4px 10px", borderRadius: 999, fontSize: 12,
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

          {/* Result section — pilot's named outputs land FIRST */}
          {hasResult && <StepRibbon steps={steps} />}

          {/* 1. Rejection-probability score (the headline output) */}
          {done && <ScoreBlock score={done.score} band={done.band} intent={done.intent} />}

          {/* 2. Cure-path checklist (the action a staffer takes) */}
          {done && <CurePath items={done.cure_path} citations={citations} />}

          {/* 3. Supporting reasoning */}
          {hasResult && (
            <>
              <div style={{ marginTop: 18, fontSize: 12, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.06, color: "var(--ink-3)" }}>Reasoning</div>
              <div style={{ marginTop: 6, padding: 18, background: "var(--canvas)", border: "1px solid var(--border)", borderRadius: 8, lineHeight: 1.65, fontSize: 14, color: "var(--ink-1)", whiteSpace: "pre-wrap" }}>
                {answer || (validating ? <span style={{ color: "var(--ink-3)" }}>…</span> : null)}
              </div>
            </>
          )}

          {/* 4. Citations */}
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
