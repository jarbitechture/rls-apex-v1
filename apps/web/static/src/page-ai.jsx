// AI Co-pilot — chat-first with agent mode selector + knowledge sidebar
const { I, UI, SAMPLE } = window;
const { Pill, Btn, Card, TextInput, Bar } = UI;
const { PageHeader } = window;

const AGENTS = [
  { id: "policy", label: "PolicyMatcher", desc: "Maps your draft against §125, §166, §163 statutes & County code", color: "var(--primary)", icon: <I.Graph size={13} /> },
  { id: "precedent", label: "PrecedentRetriever", desc: "Finds relevant prior RLS opinions + Florida case law", color: "var(--info)", icon: <I.Library size={13} /> },
  { id: "compliance", label: "ComplianceGrader", desc: "Scores draft against the 8 compliance lanes, line-by-line", color: "var(--warning)", icon: <I.Shield size={13} /> },
  { id: "reviser", label: "Reviser", desc: "Rewrites for clarity, removes ex parte risk, tightens scope", color: "var(--success)", icon: <I.Edit size={13} /> },
];

const QUICK = [
  "Apply NIST AI RMF to this matter",
  "Find rejection precedents for STR ordinances",
  "Re-classify risk after BIE review",
  "Draft transmittal email (no body content)",
  "Suggest governing authorities for §125.66(3)(c)",
];

const TURNS = [
  { who: "user", text: "Re-evaluate risk on RLS-26-0141 after the BIE worksheet was added. Anything change?" },
  {
    who: "ai", agent: "compliance", lineage: "ln-26-0141-7c4a",
    text: "Risk classification updated **Medium → High**. The BIE worksheet (v2) adds line items 14–22 establishing a private right of action for adjacent property owners. Two issues:",
    cites: [
      { tag: "Fla. Stat.", k: "§163.31801", line: "Likely preempts municipal creation of new private rights of action without express delegation." },
      { tag: "Case", k: "Burns v. Palm Beach Cty., 999 So. 2d 1086", line: "Cited for analogous land-use private-action overreach in 2018." },
    ],
    actions: [
      { label: "Apply to RLS-26-0141", icon: <I.Check size={11} stroke={2.5} /> },
      { label: "View redline" },
      { label: "See full reasoning" },
    ],
  },
  { who: "user", text: "Draft a one-paragraph caveat for the opinion explaining the risk." },
  {
    who: "ai", agent: "reviser", lineage: "ln-26-0141-7c4b",
    text: "Drafted. Reads as plain advisory language, no legal advice given to drafters:",
    block: '"While the proposed amendment\'s minimum-stay and permit-fee provisions appear within the County\'s home-rule authority under Fla. Stat. §125.66, lines 14–22 — establishing a private right of action for adjacent property owners — raise a significant preemption concern under §163.31801 and the rationale articulated in Burns v. Palm Beach County. We recommend either (a) striking the private-action language prior to first reading, or (b) tying the right to existing nuisance statutes already authorized at the County level."',
    actions: [
      { label: "Insert into opinion", icon: <I.Check size={11} stroke={2.5} /> },
      { label: "Tighten" },
      { label: "More formal" },
    ],
  },
];

const Turn = ({ t }) => {
  if (t.who === "user") {
    return (
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 16 }}>
        <div style={{
          maxWidth: 560, padding: "9px 13px",
          background: "color-mix(in oklab, var(--primary) 8%, white)",
          border: "1px solid color-mix(in oklab, var(--primary) 18%, white)",
          borderRadius: "12px 12px 4px 12px",
          fontSize: 13, lineHeight: 1.55, color: "var(--ink)",
        }}>{t.text}</div>
      </div>
    );
  }
  const agent = AGENTS.find(a => a.id === t.agent);
  return (
    <div style={{ display: "flex", gap: 10, marginBottom: 18 }}>
      <div style={{
        width: 28, height: 28, borderRadius: 6, flex: "none",
        background: `color-mix(in oklab, ${agent.color} 14%, white)`,
        color: agent.color, display: "grid", placeItems: "center",
        border: `1px solid color-mix(in oklab, ${agent.color} 25%, white)`,
      }}>{agent.icon}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: agent.color }}>{agent.label}</span>
          <span className="mono" style={{ fontSize: 10, color: "var(--ink-4)" }}>· lineage {t.lineage}</span>
          <Pill tone="ghost" style={{ border: "1px solid var(--border)", padding: "0 5px", fontSize: 9.5 }}>haiku-4-5</Pill>
        </div>
        <div style={{ fontSize: 13, lineHeight: 1.6, color: "var(--ink)" }} dangerouslySetInnerHTML={{ __html: t.text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>') }} />
        {t.cites && (
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 10 }}>
            {t.cites.map((c, i) => (
              <div key={i} style={{
                display: "grid", gridTemplateColumns: "auto 1fr",
                gap: 10, padding: "7px 10px",
                background: "var(--canvas)",
                border: "1px solid var(--border)", borderRadius: 6,
                fontSize: 11.5,
              }}>
                <Pill tone="info" dot style={{ fontFamily: "var(--mono)" }}>{c.k}</Pill>
                <span style={{ color: "var(--ink-2)" }}>{c.line}</span>
              </div>
            ))}
          </div>
        )}
        {t.block && (
          <div className="serif" style={{
            marginTop: 10, padding: "11px 14px",
            background: "color-mix(in oklab, var(--muted) 60%, white)",
            border: "1px solid var(--border)", borderRadius: 8,
            fontSize: 13, lineHeight: 1.65, color: "var(--ink)",
            fontStyle: "italic",
          }}>{t.block}</div>
        )}
        {t.actions && (
          <div style={{ display: "flex", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
            {t.actions.map((a, i) => (
              <Btn key={i} variant={i === 0 ? "primary" : "default"} size="sm" icon={a.icon}>{a.label}</Btn>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

const AiPage = ({ go }) => {
  const [agent, setAgent] = React.useState("compliance");
  const [input, setInput] = React.useState("");
  const [turns, setTurns] = React.useState(TURNS);
  const [busy, setBusy] = React.useState(false);

  const send = (text) => {
    const q = (text ?? input).trim();
    if (!q) return;
    setInput("");
    const userTurn = { who: "user", text: q };
    setTurns(t => [...t, userTurn]);
    setBusy(true);
    setTimeout(() => {
      const a = AGENTS.find(a => a.id === agent);
      setTurns(t => [...t, {
        who: "ai", agent, lineage: `ln-${Math.random().toString(16).slice(2, 8)}`,
        text: `Routing through **${a.label}** … here's a stubbed reply for "${q.slice(0, 60)}". In production this calls the Hono RAG gateway with grounded retrieval.`,
        actions: [{ label: "Refine", icon: <I.Spark size={11} /> }, { label: "Cite sources" }],
      }]);
      setBusy(false);
    }, 700);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <PageHeader
        title="Validate"
        sub="Pre-check a draft RLS against the County Attorney corpus before submission. Citations are real; LLM is mocked until SGLang lands."
        right={<>
          <Btn variant="default" size="sm" icon={<I.Hash size={13} />}>View lineage</Btn>
          <Btn variant="default" size="sm" icon={<I.Settings size={13} />}>Gateway settings</Btn>
        </>}
      />

      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "minmax(0, 1fr) 280px", overflow: "hidden" }}>
        {/* MAIN chat */}
        <div style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {/* agent selector strip — compact single-row */}
          <div style={{ flex: "none", display: "flex", gap: 6, padding: "8px 20px", borderBottom: "1px solid var(--border)", background: "var(--canvas)", overflowX: "auto", alignItems: "center" }}>
            <span style={{ fontSize: 10.5, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.6, color: "var(--ink-3)", marginRight: 4, flex: "none" }}>Agent</span>
            {AGENTS.map(a => {
              const active = agent === a.id;
              return (
                <button key={a.id} onClick={() => setAgent(a.id)} title={a.desc} style={{
                  display: "inline-flex", alignItems: "center", gap: 5,
                  padding: "5px 10px", flex: "none",
                  background: active ? `color-mix(in oklab, ${a.color} 10%, white)` : "var(--canvas)",
                  border: `1.5px solid ${active ? a.color : "var(--border)"}`,
                  borderRadius: 999, cursor: "pointer",
                  fontSize: 11.5, fontWeight: 600, color: active ? a.color : "var(--ink-2)",
                  transition: "all 120ms",
                }}>
                  {a.icon}{a.label}
                </button>
              );
            })}
            <span style={{ flex: 1 }} />
            <span style={{ fontSize: 11, color: "var(--ink-3)", flex: "none", whiteSpace: "nowrap" }}>{AGENTS.find(a => a.id === agent).desc}</span>
          </div>

          {/* turns */}
          <div style={{ flex: "1 1 0", minHeight: 0, overflowY: "auto", padding: "20px 28px" }}>
            {turns.map((t, i) => <Turn key={i} t={t} />)}
            {busy && (
              <div style={{ display: "flex", gap: 10, alignItems: "center", color: "var(--ink-3)", fontSize: 12 }}>
                <span style={{ display: "inline-flex", gap: 3 }}>
                  <span style={{ width: 5, height: 5, borderRadius: 999, background: "var(--ink-4)", animation: "twkpulse 1.2s ease-in-out infinite" }} />
                  <span style={{ width: 5, height: 5, borderRadius: 999, background: "var(--ink-4)", animation: "twkpulse 1.2s ease-in-out infinite .15s" }} />
                  <span style={{ width: 5, height: 5, borderRadius: 999, background: "var(--ink-4)", animation: "twkpulse 1.2s ease-in-out infinite .3s" }} />
                </span>
                retrieving from Qdrant · embedding query · grounding…
              </div>
            )}
          </div>

          {/* quick prompts */}
          <div style={{ flex: "none", padding: "8px 20px", borderTop: "1px solid var(--border)", display: "flex", gap: 6, overflowX: "auto", whiteSpace: "nowrap" }}>
            {QUICK.map(q => (
              <button key={q} onClick={() => send(q)} style={{
                padding: "4px 10px", background: "var(--muted)",
                border: "1px solid var(--border)", borderRadius: 999,
                fontSize: 11.5, color: "var(--ink-2)", cursor: "pointer",
                flex: "none",
              }}>{q}</button>
            ))}
          </div>

          {/* composer */}
          <div style={{ flex: "none", padding: "10px 20px 16px", borderTop: "1px solid var(--border)", background: "var(--canvas)" }}>
            <div style={{
              display: "flex", alignItems: "flex-end", gap: 8,
              border: "1.5px solid var(--border-strong)", borderRadius: 10,
              padding: 8, background: "var(--canvas)",
            }}>
              <I.Sparkles size={14} style={{ color: AGENTS.find(a => a.id === agent).color, marginLeft: 4, marginBottom: 6 }} />
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
                placeholder={`Ask ${AGENTS.find(a => a.id === agent).label}… ⏎ to send`}
                rows={1}
                style={{
                  flex: 1, border: "none", outline: "none", resize: "none",
                  fontSize: 13, lineHeight: 1.5, fontFamily: "inherit", padding: "4px 0",
                  background: "transparent", color: "var(--ink)",
                }}
              />
              <Btn variant="primary" size="sm" icon={<I.Send size={12} />} onClick={() => send()}>Send</Btn>
            </div>
            <div style={{ fontSize: 10.5, color: "var(--ink-4)", marginTop: 6 }}>
              All replies are stamped with a lineage ID and written to the matter's audit chain. Co-pilot does not provide legal advice.
            </div>
          </div>
        </div>

        {/* SIDEBAR knowledge */}
        <div style={{ borderLeft: "1px solid var(--border)", background: "color-mix(in oklab, var(--muted) 30%, white)", overflowY: "auto", padding: 14 }}>
          <div style={{ fontSize: 10.5, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.6, color: "var(--ink-3)", marginBottom: 8 }}>Active matter</div>
          <Card padding={12} style={{ marginBottom: 14 }}>
            <div className="mono" style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-2)" }}>RLS-26-0141</div>
            <div style={{ fontSize: 12.5, fontWeight: 500, marginTop: 3, lineHeight: 1.4 }}>STR amendment §125.66(3)(c)</div>
            <div style={{ display: "flex", gap: 5, marginTop: 8, flexWrap: "wrap" }}>
              <Pill tone="primary" dot>Land Use</Pill>
              <Pill tone="warning">BIE</Pill>
            </div>
          </Card>

          <div style={{ fontSize: 10.5, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.6, color: "var(--ink-3)", marginBottom: 8 }}>Knowledge base</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: 14 }}>
            {[
              { icon: <I.Graph size={13} />, label: "Policy Graph", n: "11 nodes" },
              { icon: <I.Library size={13} />, label: "Precedent Library", n: "84 opinions" },
              { icon: <I.Database size={13} />, label: "KPI Analytics", n: "FY26" },
              { icon: <I.Doc size={13} />, label: "County Code 2024", n: "indexed" },
            ].map(item => (
              <button key={item.label} style={{
                display: "flex", alignItems: "center", gap: 8,
                padding: "7px 9px", textAlign: "left",
                background: "transparent", border: "none", borderRadius: 5,
                fontSize: 12, color: "var(--ink-2)", cursor: "pointer",
                width: "100%",
              }}>
                <span style={{ color: "var(--primary)" }}>{item.icon}</span>
                <span style={{ flex: 1 }}>{item.label}</span>
                <span style={{ fontSize: 10.5, color: "var(--ink-4)" }}>{item.n}</span>
              </button>
            ))}
          </div>

          <div style={{ fontSize: 10.5, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.6, color: "var(--ink-3)", marginBottom: 8 }}>Retrieval · this turn</div>
          <Card padding={12}>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 11.5 }}>
              {[
                { k: "§163.31801 — Preemption", score: 0.94 },
                { k: "Burns v. Palm Beach Cty.", score: 0.88 },
                { k: "RLS-25-0098 (similar STR)", score: 0.82 },
                { k: "§125.66(3)(c) BIE rule", score: 0.79 },
              ].map(r => (
                <div key={r.k} style={{ display: "grid", gridTemplateColumns: "1fr 60px 30px", gap: 6, alignItems: "center" }}>
                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "var(--ink-2)" }}>{r.k}</span>
                  <Bar pct={r.score * 100} h={3} />
                  <span className="num mono" style={{ fontSize: 10.5, color: "var(--ink-3)", textAlign: "right" }}>{r.score.toFixed(2)}</span>
                </div>
              ))}
            </div>
          </Card>

          <div style={{ marginTop: 14, padding: 10, background: "var(--canvas)", border: "1px dashed var(--border-strong)", borderRadius: 8, fontSize: 11, color: "var(--ink-3)", lineHeight: 1.5 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 5, color: "var(--ink-2)", fontWeight: 600, marginBottom: 4 }}>
              <I.Shield size={11} /> Guardrails active
            </div>
            no legal advice · cites required · lineage stamped · gateway auth ok
          </div>
        </div>
      </div>

      <style>{`@keyframes twkpulse { 0%, 80%, 100% { opacity: 0.3; } 40% { opacity: 1; } }`}</style>
    </div>
  );
};

window.AiPage = AiPage;
