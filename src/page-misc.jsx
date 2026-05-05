// remaining workflow pages — Inbox, BIE, Code Enforcement, Policy Graph, Precedents, KPI, Drafts
const { I, UI, SAMPLE } = window;
const { Pill, StatusPill, UrgencyPill, Bar, Btn, Card, Sparkline, Donut } = UI;
const { PageHeader } = window;

// ── Inbox ─────────────────────────────────────────────────────────
const NOTIFS = [
  { time: "11:42", urgent: true, type: "submitted", id: "RLS-26-0142", who: "M. Hernandez", text: "submitted a new code enforcement matter — needs acknowledgment", read: false },
  { time: "11:29", urgent: true, type: "ai", id: "RLS-26-0141", who: "AI Co-pilot", text: "re-classified risk Medium → High after BIE review of §163.31801 preemption", read: false },
  { time: "10:11", urgent: false, type: "complete", id: "RLS-26-0139", who: "L. Okafor", text: "marked Kimley-Horn contract amendment complete", read: false },
  { time: "09:48", urgent: false, type: "ack", id: "RLS-26-0136", who: "R. Patel", text: "acknowledged ADA accommodation grievance", read: true },
  { time: "Yesterday", urgent: false, type: "assign", id: "RLS-26-0138", who: "K. Tran", text: "accepted routing to Land Use team", read: true },
  { time: "Yesterday", urgent: false, type: "submitted", id: "RLS-26-0140", who: "Sheriff's Office", text: "submitted public records matter — body-cam retention", read: true },
  { time: "May 3", urgent: false, type: "audit", id: "system", who: "System", text: "hash chain auto-verified · 14,302 entries · OK", read: true },
];

const Inbox = ({ go }) => {
  const [tab, setTab] = React.useState("all");
  const filtered = NOTIFS.filter(n => tab === "all" || (tab === "unread" && !n.read) || (tab === "urgent" && n.urgent));
  const types = {
    submitted: { color: "var(--info)", icon: <I.Send size={11} /> },
    ack: { color: "var(--warning)", icon: <I.Eye size={11} /> },
    assign: { color: "var(--primary)", icon: <I.Users size={11} /> },
    complete: { color: "var(--success)", icon: <I.Check size={11} stroke={2.5} /> },
    ai: { color: "var(--primary)", icon: <I.Sparkles size={11} /> },
    audit: { color: "var(--ink-3)", icon: <I.Shield size={11} /> },
  };
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <PageHeader title="Inbox" sub="Notifications across the County legal team · 3 unread"
        right={<><Btn variant="default" size="sm" icon={<I.Check size={13} />}>Mark all read</Btn><Btn variant="default" size="sm" icon={<I.Settings size={13} />}>Preferences</Btn></>} />
      <div style={{ display: "flex", gap: 0, padding: "0 20px", borderBottom: "1px solid var(--border)" }}>
        {[["all","All",NOTIFS.length],["unread","Unread",NOTIFS.filter(n=>!n.read).length],["urgent","Urgent",NOTIFS.filter(n=>n.urgent).length]].map(([id,label,n]) => (
          <button key={id} onClick={() => setTab(id)} style={{
            background: "none", border: "none", padding: "10px 12px",
            fontSize: 12.5, fontWeight: tab===id?600:500, color: tab===id?"var(--ink)":"var(--ink-3)",
            borderBottom: `2px solid ${tab===id?"var(--primary)":"transparent"}`, cursor: "pointer", display: "flex", alignItems: "center", gap: 6,
          }}>
            {label}
            <span style={{ fontSize: 10.5, padding: "0 5px", borderRadius: 999, background: tab===id?"color-mix(in oklab, var(--primary) 14%, white)":"var(--muted-2)", color: tab===id?"var(--primary-ink)":"var(--ink-3)", fontWeight: 600 }}>{n}</span>
          </button>
        ))}
      </div>
      <div style={{ flex: 1, overflowY: "auto", background: "var(--canvas)" }}>
        {filtered.map((n, i) => {
          const t = types[n.type];
          return (
            <div key={i} onClick={() => go("detail", n.id)} style={{
              display: "grid", gridTemplateColumns: "20px 80px 1fr 100px 24px",
              gap: 12, alignItems: "center", padding: "11px 20px",
              borderBottom: "1px solid var(--border)",
              background: n.read ? "transparent" : "color-mix(in oklab, var(--primary) 3%, white)",
              cursor: "pointer", fontSize: 12.5,
            }} onMouseEnter={(e) => e.currentTarget.style.background = "var(--muted)"}
               onMouseLeave={(e) => e.currentTarget.style.background = n.read ? "transparent" : "color-mix(in oklab, var(--primary) 3%, white)"}>
              <span style={{ width: 8, height: 8, borderRadius: 999, background: n.read ? "transparent" : (n.urgent ? "var(--destructive)" : "var(--primary)") }} />
              <span className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)" }}>{n.time}</span>
              <div style={{ minWidth: 0, lineHeight: 1.4 }}>
                <span style={{ fontWeight: 600, color: "var(--ink)" }}>{n.who}</span>{" "}
                <span style={{ color: "var(--ink-2)" }}>{n.text}</span>
              </div>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 5, color: t.color, fontSize: 11, fontWeight: 600 }}>
                {t.icon}<span className="mono" style={{ color: "var(--ink-3)" }}>{n.id}</span>
              </span>
              <I.Chevron size={13} style={{ color: "var(--ink-4)" }} />
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ── BIE Worksheet workflow ────────────────────────────────────────
const BIE_QUESTIONS = [
  { id: "purpose", q: "Purpose of the proposed ordinance", a: "Restrict short-term rentals to a 7-night minimum in coastal residential zones and establish an annual permit fee tied to occupancy load.", count: 142, max: 500 },
  { id: "entities", q: "Entities likely to be affected", a: "Approximately 1,840 STR operators in coastal R-1 / R-1A zones. Largest exposure: ~120 commercial-grade hosts (>4 units).", count: 178, max: 500 },
  { id: "direct", q: "Estimated direct compliance costs", a: "Permit fee scales $250–$1,800 by occupancy. Estimated avg cost increase $640/unit/yr.", count: 96, max: 400 },
  { id: "indirect", q: "Estimated indirect / opportunity costs", a: "Reduced booking velocity in peak season — modeled 8–14% lodging-tax revenue softening based on Sarasota County's 2023 comparable.", count: 158, max: 400 },
  { id: "alternatives", q: "Alternatives considered", a: "(1) Status quo with enforcement increase, (2) registration-only no minimum-stay, (3) tiered approach by zone density.", count: 132, max: 400 },
];

const Bie = ({ go }) => {
  const [active, setActive] = React.useState("entities");
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <PageHeader title="BIE Worksheets" sub="Business Impact Estimate per §125.66(3)(c) · 4 active worksheets · 1 overdue"
        right={<><Btn variant="default" size="sm" icon={<I.Calendar size={13} />}>Posting calendar</Btn><Btn variant="primary" size="sm" icon={<I.Plus size={13} stroke={2} />}>New worksheet</Btn></>} />
      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "260px minmax(0, 1fr)", overflow: "hidden" }}>
        <div style={{ borderRight: "1px solid var(--border)", overflowY: "auto", padding: 10, background: "color-mix(in oklab, var(--muted) 30%, white)" }}>
          {[
            { id: "str", n: "RLS-26-0141", title: "STR amendment §125.66(3)(c)", deadline: "May 31", days: "+18d", status: "active", pct: 70 },
            { id: "tree", n: "RLS-26-0119", title: "Tree canopy preservation rev.", deadline: "May 14", days: "+1d", status: "warn", pct: 88 },
            { id: "dock", n: "RLS-26-0098", title: "Dock construction permit fees", deadline: "Apr 28", days: "−5d", status: "overdue", pct: 100 },
            { id: "noise", n: "RLS-26-0084", title: "Coastal noise ordinance", deadline: "Jun 12", days: "+30d", status: "draft", pct: 22 },
          ].map(w => (
            <button key={w.id} onClick={() => setActive(w.id)} style={{
              display: "flex", flexDirection: "column", gap: 4,
              padding: "9px 10px", margin: "0 0 4px", width: "100%", textAlign: "left",
              background: active === w.id ? "var(--canvas)" : "transparent",
              border: `1px solid ${active === w.id ? "var(--border-strong)" : "transparent"}`,
              borderRadius: 6, cursor: "pointer",
              boxShadow: active === w.id ? "var(--shadow-xs)" : "none",
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 6 }}>
                <span className="mono" style={{ fontSize: 10.5, fontWeight: 600 }}>{w.n}</span>
                <Pill tone={w.status === "overdue" ? "danger" : w.status === "warn" ? "warning" : w.status === "draft" ? "default" : "primary"} dot>{w.days}</Pill>
              </div>
              <span style={{ fontSize: 12, fontWeight: 500, lineHeight: 1.35, color: "var(--ink)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{w.title}</span>
              <Bar pct={w.pct} h={3} color={w.status === "overdue" ? "var(--destructive)" : w.status === "warn" ? "var(--warning)" : "var(--primary)"} />
            </button>
          ))}
        </div>
        <div style={{ overflowY: "auto", padding: "20px 28px" }}>
          <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", marginBottom: 16, gap: 16 }}>
            <div>
              <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>BIE-2026-014 · linked to RLS-26-0141</div>
              <h2 className="serif" style={{ fontSize: 22, fontWeight: 600, margin: "4px 0 0", letterSpacing: -0.3 }}>Short-term rental amendment — BIE worksheet</h2>
              <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 4 }}>Posting deadline May 31 · adoption hearing Jun 19 · Planning & Zoning</div>
            </div>
            <Donut pct={70} size={56} stroke={6} color="var(--primary)" label={<span className="num" style={{ fontSize: 12, fontWeight: 700 }}>70%</span>} />
          </div>

          <Card title="Exemption check" style={{ marginBottom: 14 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
              {[
                { q: "Required by federal or state law?", a: "No", tone: "info" },
                { q: "Procedural / housekeeping only?", a: "No", tone: "info" },
                { q: "Adopting a comprehensive plan element?", a: "No", tone: "info" },
                { q: "Emergency action under §252?", a: "No", tone: "info" },
              ].map((e, i) => (
                <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr 80px", gap: 10, padding: "5px 0", borderBottom: i < 3 ? "1px dashed var(--border)" : "none", alignItems: "center" }}>
                  <span style={{ color: "var(--ink-2)" }}>{e.q}</span>
                  <Pill tone="ghost" style={{ border: "1px solid var(--border)" }} dot>{e.a}</Pill>
                </div>
              ))}
              <div style={{ marginTop: 6, padding: "8px 10px", background: "color-mix(in oklab, var(--warning) 8%, white)", border: "1px solid color-mix(in oklab, var(--warning) 22%, white)", borderRadius: 6, color: "var(--warning)", fontSize: 12, fontWeight: 500 }}>
                <I.Alert size={12} style={{ verticalAlign: "-2px", marginRight: 6 }} />
                No exemptions apply — full BIE required.
              </div>
            </div>
          </Card>

          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {BIE_QUESTIONS.map((q, i) => (
              <Card key={q.id} title={`${i + 1}. ${q.q}`} action={
                <span className="mono" style={{ fontSize: 10.5, color: q.count > q.max * 0.9 ? "var(--warning)" : "var(--ink-3)" }}>{q.count}/{q.max}</span>
              }>
                <div style={{
                  fontSize: 12.5, lineHeight: 1.55, color: "var(--ink-2)",
                  padding: "10px 12px", background: "color-mix(in oklab, var(--muted) 50%, white)",
                  border: "1px solid var(--border)", borderRadius: 6, fontFamily: "var(--serif)",
                  fontStyle: "italic",
                }}>{q.a}</div>
              </Card>
            ))}
          </div>

          <div style={{ marginTop: 16, padding: "12px 14px", display: "flex", alignItems: "center", justifyContent: "space-between", background: "var(--canvas)", border: "1px solid var(--border)", borderRadius: 8 }}>
            <div style={{ fontSize: 12.5, color: "var(--ink-2)" }}>
              <strong>Posting deadline May 31</strong> — must be on County website ≥ 14 days before adoption hearing
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <Btn variant="default" size="sm" icon={<I.Eye size={12} />}>Preview PDF</Btn>
              <Btn variant="primary" size="sm" icon={<I.Send size={12} />}>Submit for posting</Btn>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ── Code Enforcement checklist ────────────────────────────────────
const CE_ITEMS = [
  { g: "Citation history", items: [
    { l: "Initial NOV issued and served", done: true },
    { l: "Compliance period elapsed (30+ days)", done: true },
    { l: "All re-inspection notes dated", done: true },
    { l: "Photographic evidence indexed by date", done: true },
  ]},
  { g: "Special magistrate", items: [
    { l: "Order(s) attached, certified copies", done: true },
    { l: "Findings of fact reduced to writing", done: true },
    { l: "Daily fine accrual schedule", done: false },
    { l: "Lien recorded with Clerk", done: false },
  ]},
  { g: "Service & due process", items: [
    { l: "Owner of record verified via Property Appraiser", done: true },
    { l: "All occupants noticed", done: true },
    { l: "Service by certified mail or posting", done: true },
    { l: "Affidavit of service signed", done: false },
  ]},
  { g: "Litigation packet", items: [
    { l: "Title search current within 90 days", done: false },
    { l: "Code section(s) cited with version dates", done: true },
    { l: "Statement of fees, costs, and lien amount", done: false },
    { l: "Proposed order drafted (Word format)", done: true },
  ]},
];

const CodeEnforcement = ({ go }) => {
  const total = CE_ITEMS.flatMap(g => g.items).length;
  const done = CE_ITEMS.flatMap(g => g.items).filter(i => i.done).length;
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <PageHeader title="Code Enforcement Checklist" sub={`RLS-26-0142 · 4810 26th St W · ${done}/${total} items complete · blocking submission until 100%`}
        right={<><Btn variant="default" size="sm" icon={<I.Eye size={13} />}>Preview packet</Btn><Btn variant="primary" size="sm" icon={<I.Send size={13} />} disabled>Submit RLS</Btn></>} />
      <div style={{ flex: 1, overflow: "auto", padding: 20 }}>
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 320px", gap: 16 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {CE_ITEMS.map(group => {
              const g_done = group.items.filter(i => i.done).length;
              return (
                <Card key={group.g} title={group.g} action={
                  <span style={{ fontSize: 11, fontWeight: 600, color: g_done === group.items.length ? "var(--success)" : "var(--ink-3)" }} className="num">
                    {g_done}/{group.items.length}
                  </span>
                } padding={0}>
                  {group.items.map((it, i) => (
                    <div key={i} style={{
                      display: "grid", gridTemplateColumns: "20px 1fr auto",
                      gap: 10, alignItems: "center",
                      padding: "10px 14px", borderTop: i ? "1px solid var(--border)" : "none",
                      fontSize: 12.5,
                    }}>
                      <span style={{
                        width: 16, height: 16, borderRadius: 4,
                        background: it.done ? "var(--success)" : "var(--canvas)",
                        border: `1.5px solid ${it.done ? "var(--success)" : "var(--border-strong)"}`,
                        display: "grid", placeItems: "center", color: "white",
                      }}>{it.done && <I.Check size={10} stroke={3} />}</span>
                      <span style={{ color: it.done ? "var(--ink-3)" : "var(--ink)", textDecoration: it.done ? "line-through" : "none" }}>{it.l}</span>
                      {!it.done && <Btn variant="ghost" size="sm">Resolve</Btn>}
                    </div>
                  ))}
                </Card>
              );
            })}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <Card title="Property snapshot">
              <div style={{ height: 130, marginBottom: 10, borderRadius: 6, overflow: "hidden", border: "1px solid var(--border)", background: "linear-gradient(180deg, color-mix(in oklab, var(--primary) 8%, white), color-mix(in oklab, var(--accent) 8%, white))", position: "relative" }}>
                <svg width="100%" height="100%" viewBox="0 0 200 130" preserveAspectRatio="none">
                  {/* stylized parcel map */}
                  {[...Array(10)].map((_, i) => <line key={`h${i}`} x1="0" y1={i*15} x2="200" y2={i*15} stroke="rgba(0,0,0,0.05)" />)}
                  {[...Array(14)].map((_, i) => <line key={`v${i}`} x1={i*15} y1="0" x2={i*15} y2="130" stroke="rgba(0,0,0,0.05)" />)}
                  <rect x="60" y="40" width="80" height="50" fill="color-mix(in oklab, var(--warning) 30%, white)" stroke="var(--warning)" strokeWidth="2" />
                  <circle cx="100" cy="65" r="8" fill="var(--destructive)" stroke="white" strokeWidth="2" />
                </svg>
              </div>
              <div style={{ fontSize: 11.5, color: "var(--ink-3)", display: "flex", flexDirection: "column", gap: 3 }}>
                <div><strong style={{ color: "var(--ink)" }}>4810 26th St W</strong></div>
                <div>Parcel ID 0716800050 · R-1A zone</div>
                <div>Owner: Sunset Coast LLC</div>
              </div>
            </Card>
            <Card title="Violation timeline">
              <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 11.5 }}>
                {[
                  { d: "Jan 14", t: "Initial NOV — unpermitted structure" },
                  { d: "Feb 14", t: "Re-inspection — no compliance" },
                  { d: "Mar 02", t: "Special magistrate hearing" },
                  { d: "Mar 09", t: "Order with $250/day fine" },
                  { d: "Apr 23", t: "Lien filed" },
                  { d: "May 4", t: "RLS submitted" },
                ].map((e, i) => (
                  <div key={i} style={{ display: "grid", gridTemplateColumns: "60px 1fr", gap: 8, padding: "3px 0", borderBottom: i < 5 ? "1px dashed var(--border)" : "none" }}>
                    <span className="mono" style={{ color: "var(--ink-3)" }}>{e.d}</span>
                    <span style={{ color: "var(--ink-2)" }}>{e.t}</span>
                  </div>
                ))}
              </div>
            </Card>
            <Card title="Fine accrual">
              <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginBottom: 6 }}>
                <span className="num" style={{ fontSize: 22, fontWeight: 600 }}>$14,250</span>
                <span style={{ fontSize: 11, color: "var(--ink-3)" }}>57 days × $250</span>
              </div>
              <Sparkline data={[0,2,4,6,8,11,14]} w={250} h={28} stroke="var(--warning)" fill="color-mix(in oklab, var(--warning) 14%, transparent)" strokeWidth={1.6} />
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
};

// ── Policy Graph ─────────────────────────────────────────────────
const Policy = () => (
  <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
    <PageHeader title="Policy Graph" sub="Statutes, code sections, and prior opinions linked by citation"
      right={<><Btn variant="default" size="sm" icon={<I.Filter size={13} />}>Filter</Btn><Btn variant="default" size="sm" icon={<I.Search size={13} />}>Search nodes</Btn></>} />
    <div style={{ flex: 1, display: "grid", gridTemplateColumns: "minmax(0, 1fr) 300px", overflow: "hidden" }}>
      <div style={{ position: "relative", overflow: "hidden", background: "color-mix(in oklab, var(--muted) 30%, white)" }}>
        <svg width="100%" height="100%" viewBox="0 0 800 600" style={{ display: "block" }}>
          {/* edges */}
          {[
            ["str","preempt"],["str","homerule"],["str","bie"],["preempt","burns"],["preempt","phantom"],
            ["bie","posting"],["str","prior1"],["prior1","preempt"],["homerule","prior2"],["bie","prior3"],
            ["str","prior2"],
          ].map(([a,b], i) => {
            const nodes = {
              str: [400, 300], preempt: [580, 220], homerule: [240, 220], bie: [420, 460],
              burns: [700, 160], phantom: [700, 280], posting: [560, 540],
              prior1: [520, 380], prior2: [220, 380], prior3: [320, 540],
            };
            const [x1,y1] = nodes[a], [x2,y2] = nodes[b];
            return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--border-strong)" strokeWidth="1" strokeDasharray="2 3" />;
          })}
          {[
            { id: "str", x: 400, y: 300, r: 36, label: "§125.66(3)(c)", sub: "BIE rule", primary: true },
            { id: "preempt", x: 580, y: 220, r: 28, label: "§163.31801", sub: "Preemption", color: "var(--warning)" },
            { id: "homerule", x: 240, y: 220, r: 28, label: "§166.041", sub: "Home rule" },
            { id: "bie", x: 420, y: 460, r: 26, label: "BIE Worksheet", sub: "Form" },
            { id: "burns", x: 700, y: 160, r: 22, label: "Burns v. PBC", sub: "Case" },
            { id: "phantom", x: 700, y: 280, r: 22, label: "Phantom Touring", sub: "Case" },
            { id: "posting", x: 560, y: 540, r: 20, label: "Posting", sub: "Process" },
            { id: "prior1", x: 520, y: 380, r: 18, label: "RLS-25-0098", sub: "STR opinion" },
            { id: "prior2", x: 220, y: 380, r: 18, label: "RLS-25-0042", sub: "Permit fee" },
            { id: "prior3", x: 320, y: 540, r: 18, label: "RLS-24-0119", sub: "BIE prec." },
          ].map(n => (
            <g key={n.id} style={{ cursor: "pointer" }}>
              <circle cx={n.x} cy={n.y} r={n.r}
                fill={n.primary ? "var(--primary)" : n.color || "var(--canvas)"}
                stroke={n.primary ? "var(--primary)" : n.color || "var(--border-strong)"}
                strokeWidth={n.primary ? 2 : 1.5} />
              <text x={n.x} y={n.y - 2} textAnchor="middle" fontSize={n.r > 25 ? 11 : 10} fontWeight="600"
                fill={n.primary ? "white" : "var(--ink)"} fontFamily="var(--mono)">{n.label}</text>
              <text x={n.x} y={n.y + 11} textAnchor="middle" fontSize="9"
                fill={n.primary ? "rgba(255,255,255,0.85)" : "var(--ink-3)"}>{n.sub}</text>
            </g>
          ))}
        </svg>
      </div>
      <div style={{ borderLeft: "1px solid var(--border)", overflowY: "auto", padding: 14 }}>
        <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)", marginBottom: 4 }}>SELECTED</div>
        <div className="serif" style={{ fontSize: 18, fontWeight: 600, marginBottom: 4 }}>Fla. Stat. §125.66(3)(c)</div>
        <Pill tone="primary" dot>Statute</Pill>
        <p style={{ fontSize: 12.5, lineHeight: 1.55, color: "var(--ink-2)", marginTop: 12 }}>
          Establishes the Business Impact Estimate requirement for proposed county ordinances. The County must prepare a BIE before any ordinance is adopted, post it 14 days prior to the adoption hearing, and address direct/indirect costs and alternatives.
        </p>
        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: 10.5, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.6, color: "var(--ink-3)", marginBottom: 8 }}>Connections (11)</div>
          {[
            { k: "Fla. Stat. §163.31801", t: "preempts", color: "var(--warning)" },
            { k: "Fla. Stat. §166.041", t: "parallels", color: "var(--ink-3)" },
            { k: "BIE Worksheet form", t: "implements", color: "var(--primary)" },
            { k: "RLS-25-0098", t: "applied in", color: "var(--info)" },
            { k: "RLS-25-0042", t: "discussed in", color: "var(--info)" },
            { k: "Burns v. Palm Beach Cty.", t: "rationale", color: "var(--ink-3)" },
          ].map(c => (
            <div key={c.k} style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: 10, padding: "5px 0", borderBottom: "1px dashed var(--border)", fontSize: 11.5, alignItems: "center" }}>
              <Pill tone="ghost" style={{ background: c.color, color: "white", padding: "1px 6px", fontSize: 9.5 }}>{c.t}</Pill>
              <span className="mono" style={{ color: "var(--ink-2)" }}>{c.k}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  </div>
);

// ── Precedents library ──────────────────────────────────────────
const PRECEDENTS = [
  { id: "RLS-25-0098", title: "Short-term rental zoning amendment — first review", team: "Land Use", date: "2025-09-12", risk: "Medium", outcome: "Approved with revisions", relevance: 96, tags: ["STR","§125.66","BIE"] },
  { id: "RLS-24-0287", title: "Vacation rental occupancy cap challenge", team: "Land Use", date: "2024-11-04", risk: "High", outcome: "Adopted", relevance: 88, tags: ["STR","Preemption"] },
  { id: "RLS-25-0042", title: "Permit fee tiered by occupancy load", team: "Land Use", date: "2025-04-22", risk: "Medium", outcome: "Approved", relevance: 82, tags: ["Permit","Fees"] },
  { id: "RLS-23-0201", title: "Private right of action — nuisance ordinance", team: "Litigation", date: "2023-08-18", risk: "High", outcome: "Revised", relevance: 79, tags: ["§163.31801","Preemption"] },
  { id: "RLS-24-0119", title: "BIE — tree canopy preservation amendment", team: "Land Use", date: "2024-06-30", risk: "Low", outcome: "Adopted", relevance: 71, tags: ["BIE"] },
  { id: "RLS-25-0156", title: "STR enforcement — coastal zone overlay", team: "Code Enforcement", date: "2025-12-08", risk: "Medium", outcome: "Adopted", relevance: 68, tags: ["STR","Coastal"] },
];

const Precedents = ({ go }) => (
  <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
    <PageHeader title="Precedent Library" sub="84 prior opinions · sorted by relevance to RLS-26-0141 (STR amendment)"
      right={<><Btn variant="default" size="sm" icon={<I.Filter size={13} />}>Filter</Btn><Btn variant="default" size="sm" icon={<I.Search size={13} />}>Search</Btn></>} />
    <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12 }}>
        {PRECEDENTS.map(p => (
          <Card key={p.id} padding={14} style={{ cursor: "pointer" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <span className="mono" style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-2)" }}>{p.id}</span>
              <span style={{ fontSize: 10.5, color: "var(--ink-3)" }}>{p.date}</span>
            </div>
            <div className="serif" style={{ fontSize: 14.5, fontWeight: 600, lineHeight: 1.35, marginBottom: 8, color: "var(--ink)" }}>{p.title}</div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
              <Pill tone="primary" dot>{p.team}</Pill>
              <Pill tone={p.risk === "High" ? "danger" : p.risk === "Medium" ? "warning" : "success"} dot>{p.risk} risk</Pill>
              <Pill tone="ghost" style={{ border: "1px solid var(--border)" }}>{p.outcome}</Pill>
            </div>
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginBottom: 10 }}>
              {p.tags.map(t => <span key={t} className="mono" style={{ fontSize: 10, padding: "1px 5px", background: "var(--muted)", color: "var(--ink-3)", borderRadius: 3 }}>{t}</span>)}
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8, alignItems: "center", paddingTop: 10, borderTop: "1px solid var(--border)" }}>
              <Bar pct={p.relevance} h={3} color="var(--primary)" />
              <span className="num" style={{ fontSize: 11, fontWeight: 600, color: "var(--primary-ink)" }}>{p.relevance}% match</span>
            </div>
          </Card>
        ))}
      </div>
    </div>
  </div>
);

// ── KPI Analytics ───────────────────────────────────────────────
const Kpi = () => {
  const months = ["Nov","Dec","Jan","Feb","Mar","Apr","May"];
  const incoming = [38, 42, 51, 47, 55, 49, 47];
  const closed   = [35, 40, 48, 49, 51, 52, 44];
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <PageHeader title="KPI Analytics" sub="FY26 · rolling 7-month view · admin-only"
        right={<><Btn variant="default" size="sm" icon={<I.Calendar size={13} />}>FY26</Btn><Btn variant="default" size="sm" icon={<I.Copy size={13} />}>Export CSV</Btn></>} />
      <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 14 }}>
          {[
            { k: "Total opened", v: 329, d: "+12%", spark: incoming, c: "var(--primary)" },
            { k: "Total closed", v: 319, d: "+18%", spark: closed, c: "var(--success)" },
            { k: "Avg turn (days)", v: 7.4, d: "−0.6", spark: [8.4,8.1,7.9,7.5,7.4,7.4,7.4], c: "var(--info)" },
            { k: "SLA compliance", v: "94%", d: "+1.2", spark: [89,91,92,93,94,93,94], c: "var(--warning)" },
          ].map(t => (
            <Card key={t.k} padding={14}>
              <div style={{ fontSize: 10.5, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.6, color: "var(--ink-3)" }}>{t.k}</div>
              <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginTop: 4 }}>
                <span className="num" style={{ fontSize: 26, fontWeight: 600, letterSpacing: -0.5 }}>{t.v}</span>
                <span className="num" style={{ fontSize: 11, fontWeight: 600, color: t.d.startsWith("+") || t.d.startsWith("−") && parseFloat(t.d) < 0 ? "var(--success)" : "var(--success)" }}>{t.d}</span>
              </div>
              <div style={{ color: t.c, marginTop: 8 }}>
                <Sparkline data={t.spark} w={220} h={30} stroke="currentColor" fill="color-mix(in oklab, currentColor 14%, transparent)" strokeWidth={1.4} />
              </div>
            </Card>
          ))}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.4fr) minmax(0, 1fr)", gap: 14, marginBottom: 14 }}>
          <Card title="Volume — incoming vs closed">
            <svg viewBox="0 0 600 200" style={{ width: "100%", height: 200 }}>
              {[40,80,120,160].map(y => <line key={y} x1="40" x2="580" y1={y} y2={y} stroke="var(--border)" strokeDasharray="2 3" />)}
              {months.map((m, i) => <text key={m} x={60 + i * 80} y="195" textAnchor="middle" fontSize="9" fill="var(--ink-4)" className="mono">{m}</text>)}
              {incoming.map((v, i) => (
                <rect key={i} x={60 + i * 80 - 14} y={180 - v * 2.5} width={12} height={v * 2.5} fill="color-mix(in oklab, var(--primary) 28%, white)" rx={2} />
              ))}
              {closed.map((v, i) => (
                <rect key={i} x={60 + i * 80 + 2} y={180 - v * 2.5} width={12} height={v * 2.5} fill="var(--accent)" rx={2} />
              ))}
              <line x1="60" x2={60 + 6 * 80} y1={180 - 7.4 * 5} y2={180 - 7.4 * 5} stroke="var(--warning)" strokeWidth="1.5" strokeDasharray="4 3" />
            </svg>
            <div style={{ display: "flex", gap: 14, justifyContent: "center", fontSize: 11, marginTop: 6 }}>
              <span style={{ display: "flex", alignItems: "center", gap: 5, color: "var(--ink-3)" }}><span style={{ width: 10, height: 10, background: "color-mix(in oklab, var(--primary) 28%, white)", borderRadius: 2 }} />Incoming</span>
              <span style={{ display: "flex", alignItems: "center", gap: 5, color: "var(--ink-3)" }}><span style={{ width: 10, height: 10, background: "var(--accent)", borderRadius: 2 }} />Closed</span>
              <span style={{ display: "flex", alignItems: "center", gap: 5, color: "var(--ink-3)" }}><span style={{ width: 10, height: 2, background: "var(--warning)" }} />Goal</span>
            </div>
          </Card>
          <Card title="Risk distribution">
            <div style={{ display: "flex", height: 14, borderRadius: 7, overflow: "hidden", marginBottom: 14, boxShadow: "inset 0 0 0 1px var(--border)" }}>
              <div style={{ flex: 58, background: "var(--success)" }} />
              <div style={{ flex: 30, background: "var(--warning)" }} />
              <div style={{ flex: 12, background: "var(--destructive)" }} />
            </div>
            {[["Low",58,"var(--success)"],["Medium",30,"var(--warning)"],["High",12,"var(--destructive)"]].map(([l,p,c]) => (
              <div key={l} style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 8, padding: "6px 0", borderBottom: "1px dashed var(--border)", fontSize: 12 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 6 }}><span style={{ width: 8, height: 8, background: c, borderRadius: 2 }} />{l}</span>
                <span className="num" style={{ fontWeight: 600 }}>{p}%</span>
              </div>
            ))}
          </Card>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
          <Card title="Top requesting departments">
            {[["Planning & Zoning",58],["Code Enforcement",42],["Sheriff",31],["Public Works",28],["Procurement",24],["Library",18]].map(([d,n]) => (
              <div key={d} style={{ display: "grid", gridTemplateColumns: "1fr 100px 24px", gap: 8, padding: "5px 0", fontSize: 11.5, alignItems: "center" }}>
                <span style={{ color: "var(--ink-2)" }}>{d}</span>
                <Bar pct={(n/58)*100} h={3} />
                <span className="num" style={{ fontWeight: 600, textAlign: "right" }}>{n}</span>
              </div>
            ))}
          </Card>
          <Card title="Median time-to-acknowledge">
            <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
              <span className="num" style={{ fontSize: 28, fontWeight: 600, letterSpacing: -0.5 }}>4.1</span>
              <span style={{ fontSize: 12, color: "var(--ink-3)" }}>hours · target 8</span>
            </div>
            <div style={{ marginTop: 8, color: "var(--success)" }}>
              <Sparkline data={[6.2,5.8,5.4,4.9,4.6,4.2,4.1]} w={240} h={32} stroke="currentColor" fill="color-mix(in oklab, currentColor 14%, transparent)" strokeWidth={1.4} />
            </div>
            <div style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 6 }}>Down 34% vs FY25 — primarily inbox-routing automation</div>
          </Card>
          <Card title="AI co-pilot adoption">
            <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
              <Donut pct={71} size={72} stroke={8} color="var(--primary)" label={<span className="num" style={{ fontSize: 13, fontWeight: 700 }}>71%</span>} />
              <div style={{ flex: 1, fontSize: 11.5, lineHeight: 1.55 }}>
                <div style={{ display: "flex", justifyContent: "space-between" }}><span style={{ color: "var(--ink-3)" }}>Drafts assisted</span><span className="num" style={{ fontWeight: 600 }}>71%</span></div>
                <div style={{ display: "flex", justifyContent: "space-between" }}><span style={{ color: "var(--ink-3)" }}>Daily active users</span><span className="num" style={{ fontWeight: 600 }}>23/31</span></div>
                <div style={{ display: "flex", justifyContent: "space-between" }}><span style={{ color: "var(--ink-3)" }}>Avg lineage / matter</span><span className="num" style={{ fontWeight: 600 }}>5.4</span></div>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

// ── Drafts list ────────────────────────────────────────────────
const Drafts = ({ go }) => {
  const drafts = [
    { id: "DRAFT-008", title: "STR amendment §125.66(3)(c)", lastEdit: "3s ago", completeness: 78, type: "Ordinance" },
    { id: "DRAFT-007", title: "Stormwater utility fee methodology", lastEdit: "Yesterday", completeness: 42, type: "Litigation" },
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <PageHeader title="Drafts" sub="Auto-saved RLS submissions in progress"
        right={<Btn variant="primary" size="sm" icon={<I.Plus size={13} stroke={2} />} onClick={() => go("wizard")}>New RLS</Btn>} />
      <div style={{ flex: 1, overflow: "auto", padding: 16 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12 }}>
          {drafts.map(d => (
            <Card key={d.id} padding={14} style={{ cursor: "pointer" }}>
              <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>{d.id} · auto-saved {d.lastEdit}</div>
              <div className="serif" style={{ fontSize: 16, fontWeight: 600, margin: "6px 0 8px", lineHeight: 1.3 }}>{d.title}</div>
              <Pill tone="primary" dot>{d.type}</Pill>
              <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 8 }}>
                <Bar pct={d.completeness} h={4} color={d.completeness >= 80 ? "var(--success)" : "var(--warning)"} />
                <span className="num" style={{ fontSize: 11.5, fontWeight: 600, minWidth: 36, textAlign: "right" }}>{d.completeness}%</span>
                <Btn variant="primary" size="sm" iconRight={<I.Arrow size={12} />} onClick={(e) => { e.stopPropagation(); go("wizard"); }}>Continue</Btn>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
};

window.Inbox = Inbox;
window.Bie = Bie;
window.CodeEnforcement = CodeEnforcement;
window.Policy = Policy;
window.Precedents = Precedents;
window.Kpi = Kpi;
window.Drafts = Drafts;
