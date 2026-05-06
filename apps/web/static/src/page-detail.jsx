// RLS detail with timeline
const { I, UI, SAMPLE } = window;
const { Pill, StatusPill, UrgencyPill, Bar, Btn, Card, Donut } = UI;

const TimelineEvent = ({ time, who, action, status, expanded, isLast, hashEntry }) => {
  const colors = {
    submit: "var(--info)", ack: "var(--warning)", assign: "var(--primary)", complete: "var(--success)", ai: "var(--primary)", note: "var(--ink-3)",
  };
  const c = colors[status] || "var(--ink-3)";
  return (
    <div style={{ display: "grid", gridTemplateColumns: "60px 22px 1fr", gap: 10, position: "relative" }}>
      <div className="mono" style={{ fontSize: 10.5, color: "var(--ink-4)", paddingTop: 4, textAlign: "right" }}>{time}</div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
        <span style={{ width: 10, height: 10, borderRadius: 999, background: c, marginTop: 6, boxShadow: `0 0 0 3px color-mix(in oklab, ${c} 18%, transparent)` }} />
        {!isLast && <div style={{ width: 1, flex: 1, background: "var(--border)", marginTop: 4, minHeight: 30 }} />}
      </div>
      <div style={{ paddingBottom: 18, minWidth: 0 }}>
        <div style={{ fontSize: 12.5, lineHeight: 1.4 }}>
          <span style={{ fontWeight: 600, color: "var(--ink)" }}>{who}</span> <span style={{ color: "var(--ink-2)" }}>{action}</span>
        </div>
        {expanded && <div style={{ fontSize: 11.5, color: "var(--ink-3)", marginTop: 4, lineHeight: 1.5 }}>{expanded}</div>}
        {hashEntry && (
          <div className="mono" style={{ fontSize: 10, color: "var(--ink-4)", marginTop: 5, display: "flex", gap: 8 }}>
            <span>chain</span><span>· {hashEntry}</span>
          </div>
        )}
      </div>
    </div>
  );
};

const Detail = ({ id, go }) => {
  const s = SAMPLE.submissions.find(x => x.id === id) || SAMPLE.submissions[1];
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      {/* breadcrumb header */}
      <div style={{ padding: "12px 20px", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", background: "var(--bg)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button onClick={() => go("submissions")} style={{ background: "none", border: "none", color: "var(--ink-3)", fontSize: 12, cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}>
            <I.ArrowL size={13} /> Submissions
          </button>
          <span style={{ color: "var(--ink-4)" }}>/</span>
          <span className="mono" style={{ fontSize: 12, fontWeight: 600 }}>{s.id}</span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Btn variant="ghost" size="sm" icon={<I.Copy size={13} />}>Copy link</Btn>
          <Btn variant="default" size="sm" icon={<I.Eye size={13} />}>Preview transmittal</Btn>
          <Btn variant="default" size="sm" icon={<I.Send size={13} />}>Reassign</Btn>
          <Btn variant="primary" size="sm" icon={<I.Check size={13} stroke={2.5} />}>Mark complete</Btn>
        </div>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: 20 }}>
        {/* matter header */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 16, gap: 16 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", gap: 6, marginBottom: 6, flexWrap: "wrap" }}>
              <StatusPill status={s.status} />
              <UrgencyPill urgency={s.urgency} />
              <Pill tone="ghost" style={{ border: "1px solid var(--border)" }}>{s.type}</Pill>
              {s.bie && <Pill tone="warning">BIE required</Pill>}
              <Pill tone="primary" dot>{s.team}</Pill>
            </div>
            <h1 className="serif" style={{ fontSize: 24, fontWeight: 600, margin: "6px 0 10px", letterSpacing: -0.4, color: "var(--ink)", lineHeight: 1.4 }}>{s.title}</h1>
            <div style={{ fontSize: 12.5, color: "var(--ink-3)" }}>
              Submitted by <strong style={{ color: "var(--ink-2)" }}>{s.requester}</strong> · {s.department} · <span className="mono">{s.submitted}</span>
            </div>
          </div>
          <div style={{
            display: "grid", gridTemplateColumns: "auto auto auto",
            gap: "4px 18px",
            padding: "10px 14px",
            background: "var(--canvas)", border: "1px solid var(--border)", borderRadius: 8,
            fontSize: 11.5,
          }}>
            <span style={{ color: "var(--ink-3)" }}>Working days left</span><span style={{ color: "var(--ink-3)" }}>Risk</span><span style={{ color: "var(--ink-3)" }}>Completeness</span>
            <span className="num" style={{ fontSize: 18, fontWeight: 600, color: s.workingDays <= 2 ? "var(--warning)" : "var(--ink)" }}>{s.workingDays}d</span>
            <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, fontWeight: 600 }}>
              <span style={{ width: 8, height: 8, borderRadius: 999, background: s.risk === "High" ? "var(--destructive)" : s.risk === "Medium" ? "var(--warning)" : "var(--success)" }} />
              {s.risk}
            </span>
            <span className="num" style={{ fontSize: 18, fontWeight: 600 }}>{s.completeness}%</span>
          </div>
        </div>

        {/* 2-col main */}
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.5fr) minmax(0, 1fr)", gap: 16 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <Card title="Legal question">
              <div className="serif" style={{ fontSize: 13.5, lineHeight: 1.65, color: "var(--ink)" }}>
                Council requests a legal sufficiency review of the proposed amendment to the short-term rental ordinance. The amendment introduces a 7-night minimum stay in coastal residential zones, an annual permit fee tied to occupancy load, and adds a private right of action for adjacent property owners. We need confirmation that the private right of action is constitutionally permissible under Florida home-rule preemption and that the BIE is properly noticed.
              </div>
              <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px dashed var(--border)", display: "flex", gap: 8, flexWrap: "wrap" }}>
                <Pill tone="info" dot>Fla. Stat. §125.66(3)(c)</Pill>
                <Pill tone="info" dot>Fla. Stat. §166.041</Pill>
                <Pill tone="info" dot>Phantom Touring v. Affiliated</Pill>
                <Pill tone="info" dot>Burns v. Palm Beach Cty.</Pill>
              </div>
            </Card>

            <Card title="Status timeline" action={<Pill tone="success" dot>Hash-chain verified</Pill>} padding={14}>
              <div style={{ paddingLeft: 4 }}>
                <TimelineEvent time="May 3 09:14" who="Sasha Lin" action="created the matter and uploaded 9 attachments" status="submit" hashEntry="2c8d…b71e" />
                <TimelineEvent time="May 3 09:18" who="AI Co-pilot" action="auto-classified urgency as Critical · routing → Land Use" status="ai" expanded="Reasoning: STR ordinances historically routed to Land Use (96% match · 14 prior matters). Critical due to council adoption hearing in 16 days." />
                <TimelineEvent time="May 3 10:42" who="R. Patel" action="acknowledged · added to docket" status="ack" hashEntry="4f9b…2a01" />
                <TimelineEvent time="May 3 11:20" who="R. Patel" action="assigned to self · requested BIE worksheet from Planning" status="assign" />
                <TimelineEvent time="May 4 14:08" who="S. Lin" action="uploaded BIE-worksheet-v2.pdf" status="note" />
                <TimelineEvent time="May 4 16:30" who="AI Co-pilot" action="re-classified risk: Medium → High after BIE review" status="ai" expanded="Private right of action language conflicts with §163.31801 preemption. Recommend revision before adoption." />
                <TimelineEvent time="May 5 09:02" who="R. Patel" action="drafted opinion v1 · 4 cites · 2 caveats" status="note" isLast />
              </div>
            </Card>

            <Card title="Attachments (12)" padding={0}>
              {[
                { name: "draft-ordinance-v3.docx", size: "84 KB", who: "S. Lin", when: "May 3", flag: null },
                { name: "BIE-worksheet-v2.pdf", size: "212 KB", who: "S. Lin", when: "May 4", flag: "primary" },
                { name: "council-memo.docx", size: "44 KB", who: "S. Lin", when: "May 3", flag: null },
                { name: "staff-report-redline.docx", size: "118 KB", who: "S. Lin", when: "May 3", flag: null },
                { name: "fiscal-impact-2026.xlsx", size: "76 KB", who: "Planning", when: "May 4", flag: null },
                { name: "comp-plan-citations.pdf", size: "1.2 MB", who: "S. Lin", when: "May 3", flag: null },
              ].map((a, i) => (
                <div key={i} style={{
                  display: "grid", gridTemplateColumns: "20px 1fr 80px 90px 70px",
                  gap: 12, alignItems: "center",
                  padding: "10px 14px",
                  borderTop: i ? "1px solid var(--border)" : "none",
                  fontSize: 12,
                }}>
                  <I.Doc size={13} style={{ color: "var(--ink-3)" }} />
                  <span className="mono" style={{ fontWeight: 500 }}>{a.name}</span>
                  <span style={{ color: "var(--ink-3)" }}>{a.size}</span>
                  <span style={{ color: "var(--ink-3)" }}>{a.who} · {a.when}</span>
                  {a.flag === "primary" ? <Pill tone="primary" dot>BIE</Pill> : <span />}
                </div>
              ))}
            </Card>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <Card title="Assigned">
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                <span style={{ width: 36, height: 36, borderRadius: 999, background: "linear-gradient(135deg, oklch(0.7 0.1 28), oklch(0.6 0.12 22))", color: "white", display: "grid", placeItems: "center", fontSize: 13, fontWeight: 600 }}>RP</span>
                <div style={{ flex: 1, lineHeight: 1.3 }}>
                  <div style={{ fontSize: 13, fontWeight: 600 }}>R. Patel</div>
                  <div style={{ fontSize: 11.5, color: "var(--ink-3)" }}>Land Use & Planning · 11/14 capacity</div>
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, fontSize: 11.5 }}>
                <Btn variant="default" size="sm" icon={<I.Send size={12} />}>Reassign</Btn>
                <Btn variant="default" size="sm" icon={<I.Users size={12} />}>Add reviewer</Btn>
              </div>
            </Card>

            <Card title="AI co-pilot · risk" action={<Pill tone="primary" dot>Live</Pill>}>
              <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 10 }}>
                <Donut pct={72} size={56} stroke={6} color="var(--warning)" label={<span className="num" style={{fontSize:11,fontWeight:700}}>HIGH</span>} />
                <div style={{ flex: 1, fontSize: 11.5, lineHeight: 1.5, color: "var(--ink-2)" }}>
                  Private right of action language likely preempted by <span className="mono">§163.31801</span>. Recommend striking lines 14–22 before adoption.
                </div>
              </div>
              <div style={{ borderTop: "1px solid var(--border)", paddingTop: 10, fontSize: 11.5 }}>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "3px 0" }}><span style={{ color: "var(--ink-3)" }}>Constitutional</span><span style={{ fontWeight: 600 }}>High</span></div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "3px 0" }}><span style={{ color: "var(--ink-3)" }}>Statutory</span><span style={{ fontWeight: 600, color: "var(--warning)" }}>Medium</span></div>
                <div style={{ display: "flex", justifyContent: "space-between", padding: "3px 0" }}><span style={{ color: "var(--ink-3)" }}>Procedural</span><span style={{ fontWeight: 600, color: "var(--success)" }}>Low</span></div>
              </div>
              <Btn variant="ghost" size="sm" icon={<I.Sparkles size={12} />} style={{ width: "100%", marginTop: 6, color: "var(--primary)" }}>Open co-pilot chat →</Btn>
            </Card>

            <Card title="Deadlines">
              <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 11.5 }}>
                {[
                  { label: "Initial response", date: "May 6", days: "1d", tone: "warning" },
                  { label: "Draft opinion", date: "May 12", days: "5d", tone: "default" },
                  { label: "BIE posting deadline", date: "May 31", days: "18d", tone: "default" },
                  { label: "Council adoption hearing", date: "Jun 19", days: "33d", tone: "primary" },
                ].map(d => (
                  <div key={d.label} style={{ display: "grid", gridTemplateColumns: "1fr auto auto", gap: 8, alignItems: "center", padding: "4px 0", borderBottom: "1px dashed var(--border)" }}>
                    <span style={{ color: "var(--ink-2)" }}>{d.label}</span>
                    <span className="mono" style={{ color: "var(--ink-3)" }}>{d.date}</span>
                    <Pill tone={d.tone}>{d.days}</Pill>
                  </div>
                ))}
              </div>
            </Card>

            <Card title="Hash chain">
              <div className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)", lineHeight: 1.7 }}>
                <div><span style={{ color: "var(--ink-4)" }}>head</span> 4f9b…2a01</div>
                <div><span style={{ color: "var(--ink-4)" }}>prev</span> 2c8d…b71e</div>
                <div><span style={{ color: "var(--ink-4)" }}>entries</span> 7</div>
                <div><span style={{ color: "var(--ink-4)" }}>verified</span> 2h ago</div>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};

window.Detail = Detail;
