// dashboard — dense, command-center top-of-funnel view
const { I, UI, SAMPLE } = window;
const { Pill, StatusPill, UrgencyPill, Sparkline, Bar, Btn, Card, StemChart, Donut } = UI;

const KpiTile = ({ label, value, delta, sparkData, accent, sub }) =>
<div style={{
  background: "var(--canvas)",
  border: "1px solid var(--card-border-color, var(--border))",
  borderRadius: 10,
  boxShadow: "var(--card-shadow, var(--shadow-sm))",
  padding: "12px 14px",
  display: "flex", flexDirection: "column", gap: 4,
  minWidth: 0
}}>
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
      <span style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-3)", textTransform: "uppercase", letterSpacing: 0.5 }}>{label}</span>
      {delta &&
    <span style={{ fontSize: 10.5, fontWeight: 600, color: delta.startsWith("+") ? "var(--success)" : delta.startsWith("-") ? "var(--destructive)" : "var(--ink-3)" }} className="num">{delta}</span>
    }
    </div>
    <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8 }}>
      <span className="num" style={{ fontSize: 26, fontWeight: 600, letterSpacing: -0.6, lineHeight: 1.1, color: "var(--ink)" }}>{value}</span>
      {sparkData &&
    <div style={{ color: accent || "var(--primary)" }}>
          <Sparkline data={sparkData} w={68} h={22} fill="color-mix(in oklab, currentColor 14%, transparent)" />
        </div>
    }
    </div>
    {sub && <div style={{ fontSize: 11, color: "var(--ink-3)" }}>{sub}</div>}
  </div>;


const PageHeader = ({ title, sub, right }) =>
<div style={{
  display: "flex", alignItems: "flex-end", justifyContent: "space-between",
  padding: "16px 20px 14px",
  borderBottom: "1px solid var(--border)",
  background: "var(--bg)"
}}>
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <h1 style={{ fontSize: 19, fontWeight: 600, letterSpacing: -0.3, margin: 0, color: "var(--ink)" }}>{title}</h1>
        <Pill tone="ghost" style={{ border: "1px solid var(--border)" }}>FY26 · Q3</Pill>
      </div>
      {sub && <div style={{ fontSize: 12, color: "var(--ink-3)", marginTop: 3 }}>{sub}</div>}
    </div>
    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>{right}</div>
  </div>;


const ComplianceRow = ({ rule, pct, n }) => {
  const tone = pct >= 95 ? "var(--success)" : pct >= 80 ? "var(--warning)" : "var(--destructive)";
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr auto 56px", gap: 10, alignItems: "center", padding: "7px 0", fontSize: 12 }}>
      <div style={{ color: "var(--ink-2)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={rule}>{rule}</div>
      <div style={{ width: 90 }}><Bar pct={pct} color={tone} /></div>
      <div className="num" style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-2)", textAlign: "right" }}>{pct}% <span style={{ color: "var(--ink-4)", fontWeight: 400 }}>· {n}</span></div>
    </div>);

};

const TeamLoadRow = ({ row }) => {
  const pct = row.open / row.capacity * 100;
  const tone = row.breaching > 0 ? "var(--warning)" : pct > 80 ? "var(--primary)" : "var(--success)";
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 60px 110px 30px", gap: 10, alignItems: "center", padding: "8px 0", fontSize: 12 }}>
      <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.25 }}>
        <span style={{ fontWeight: 600, color: "var(--ink)" }}>{row.team}</span>
        <span style={{ fontSize: 10.5, color: "var(--ink-3)" }}>{row.lead}</span>
      </div>
      <span className="num" style={{ fontSize: 13, fontWeight: 600 }}>{row.open}<span style={{ color: "var(--ink-4)", fontWeight: 400 }}>/{row.capacity}</span></span>
      <Bar pct={pct} color={tone} h={5} />
      {row.breaching > 0 ?
      <Pill tone="warning" style={{ padding: "1px 5px", fontSize: 10 }}>{row.breaching}</Pill> :
      <span style={{ color: "var(--ink-4)", fontSize: 10, textAlign: "right" }}>—</span>}
    </div>);

};

const SubmissionMiniRow = ({ s, onOpen }) => {
  const dl = s.workingDays;
  const dlTone = dl < 0 ? "var(--destructive)" : dl <= 2 ? "var(--warning)" : "var(--ink-3)";
  return (
    <div onClick={onOpen} style={{
      display: "grid",
      gridTemplateColumns: "92px 1fr 90px 80px 72px 24px",
      gap: 12, alignItems: "center",
      padding: "9px 12px",
      borderTop: "1px solid var(--border)",
      cursor: "pointer",
      transition: "background 80ms ease"
    }} onMouseEnter={(e) => e.currentTarget.style.background = "var(--muted)"} onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}>
      <span className="mono" style={{ fontSize: 11, fontWeight: 600, color: "var(--ink-2)" }}>{s.id}</span>
      <div style={{ display: "flex", flexDirection: "column", minWidth: 0, lineHeight: 1.3 }}>
        <span style={{ fontSize: 12.5, color: "var(--ink)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.title}</span>
        <span style={{ fontSize: 10.5, color: "var(--ink-3)", display: "flex", alignItems: "center", gap: 6 }}>
          <span>{s.requester}</span> <span style={{ color: "var(--ink-4)" }}>·</span> <span>{s.department}</span>
          {s.bie && <Pill tone="warning" style={{ padding: "0 5px", fontSize: 9.5 }}>BIE</Pill>}
        </span>
      </div>
      <StatusPill status={s.status} />
      <UrgencyPill urgency={s.urgency} />
      <span className="num" style={{ fontSize: 11.5, fontWeight: 600, color: dlTone, textAlign: "right" }}>
        {dl < 0 ? `${dl}d` : dl === 0 ? "today" : `${dl}d`}
      </span>
      <I.Chevron size={13} style={{ color: "var(--ink-4)" }} />
    </div>);

};

const ActivityItem = ({ item }) =>
<div style={{ display: "grid", gridTemplateColumns: "44px 14px 1fr", gap: 8, alignItems: "flex-start", padding: "5px 0", fontSize: 11.5, lineHeight: 1.4 }}>
    <span className="mono" style={{ color: "var(--ink-4)", fontSize: 10.5 }}>{item.time}</span>
    <span style={{
    display: "inline-block", width: 6, height: 6, borderRadius: 999, marginTop: 6,
    background: item.urgent ? "var(--destructive)" : item.who === "AI Co-pilot" ? "var(--primary)" : "var(--ink-4)"
  }} />
    <div style={{ minWidth: 0 }}>
      <span style={{ color: "var(--ink-2)" }}>{item.action}</span>
      <span style={{ color: "var(--ink-4)" }}> · </span>
      <span className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)" }}>{item.id}</span>
      <span style={{ color: "var(--ink-4)" }}> · </span>
      <span style={{ color: item.who === "AI Co-pilot" ? "var(--primary)" : "var(--ink-3)" }}>{item.who}</span>
    </div>
  </div>;


const Dashboard = ({ go }) => {
  const k = SAMPLE.dashboardKpis;
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <PageHeader
        title="Dashboard"
        sub="Tuesday · May 5, 2026 · 47 active matters · SLA 94% · 3 breaching this week"
        right={
        <>
            <Btn icon={<I.Filter size={13} />} variant="default" size="sm">Filter</Btn>
            <Btn icon={<I.Calendar size={13} />} variant="default" size="sm">Last 30 days <I.ChevronDown size={11} /></Btn>
            <Btn icon={<I.Plus size={13} stroke={2} />} variant="primary" size="sm" onClick={() => go("wizard")}>New RLS</Btn>
          </>
        } />
      

      <div style={{ flex: 1, overflow: "auto", padding: 16, color: "rgb(112, 31, 31)", opacity: "9" }}>
        {/* KPI strip */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(8, minmax(0, 1fr))", gap: 10, marginBottom: 14 }}>
          <KpiTile label="Active" value={k.active} delta="+4" sparkData={SAMPLE.incoming14} sub="opened this week 18" />
          <KpiTile label="Awaiting ack" value={k.awaitingAck} delta="+1" accent="var(--warning)" sparkData={[2, 3, 4, 3, 5, 6, 4, 5, 7, 6, 5, 4, 5, 6]} sub="median 4.1h" />
          <KpiTile label="Breaching" value={k.overdue} delta="+1" accent="var(--destructive)" sparkData={[1, 1, 2, 1, 0, 1, 2, 3, 2, 3, 2, 3, 3, 3]} sub="2 critical · 1 urgent" />
          <KpiTile label="Avg turn" value={`${k.avgTurnDays}d`} delta="-0.6" sparkData={[8.1, 7.9, 8.4, 7.7, 7.2, 7.5, 7.4]} sub="vs goal 8d" />
          <KpiTile label="SLA" value={`${k.slaPct}%`} delta="+1.2" sparkData={[91, 92, 90, 93, 94, 93, 94]} sub="rolling 30d" />
          <KpiTile label="Completeness" value={`${k.completenessAvg}%`} delta="+3" sparkData={[81, 83, 82, 85, 84, 86, 87]} sub="at first submit" />
          <KpiTile label="AI-assisted" value={`${k.aiAssisted}%`} delta="+8" sparkData={[55, 58, 61, 65, 67, 69, 71]} sub="of new RLS" />
          <KpiTile label="Hash-chain" value="OK" delta="" sparkData={[]} sub="last verify 2h ago" />
        </div>

        {/* Row: throughput + queue (wide) + activity (narrow) */}
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.05fr) minmax(0, 1fr)", gap: 14, marginBottom: 14 }}>
          <Card title="Throughput · last 14 days" action={
          <div style={{ display: "flex", gap: 14, alignItems: "center", fontSize: 11 }}>
              <span style={{ display: "flex", alignItems: "center", gap: 5, color: "var(--ink-3)" }}><span style={{ width: 8, height: 2, background: "var(--primary)" }} />Incoming</span>
              <span style={{ display: "flex", alignItems: "center", gap: 5, color: "var(--ink-3)" }}><span style={{ width: 8, height: 2, background: "var(--accent)" }} />Closed</span>
            </div>
          }>
            <ThroughputChart incoming={SAMPLE.incoming14} closed={SAMPLE.closed14} />
          </Card>

          <Card title="Recent activity" action={<a style={{ fontSize: 11, color: "var(--primary)" }}>view all →</a>} padding={10}>
            <div style={{ display: "flex", flexDirection: "column", gap: 0, paddingLeft: 4 }}>
              {SAMPLE.queue.map((q, i) => <ActivityItem key={i} item={q} />)}
            </div>
          </Card>
        </div>

        {/* Row: queue spanning + side panels */}
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.6fr) minmax(0, 1fr)", gap: 14, marginBottom: 14 }}>
          <Card
            title="Queue"
            action={<div style={{ display: "flex", gap: 6 }}>
              <Pill tone="ghost" style={{ border: "1px solid var(--border)" }} dot>All teams</Pill>
              <Pill tone="primary" dot>By deadline</Pill>
            </div>}
            padding={0}>
            
            <div style={{
              display: "grid",
              gridTemplateColumns: "92px 1fr 90px 80px 72px 24px",
              gap: 12, padding: "7px 12px",
              fontSize: 10.5, fontWeight: 600, color: "var(--ink-3)",
              textTransform: "uppercase", letterSpacing: 0.5,
              background: "var(--muted)"
            }}>
              <span>Number</span><span>Matter</span><span>Status</span><span>Urgency</span><span style={{ textAlign: "right" }}>Deadline</span><span />
            </div>
            {SAMPLE.submissions.slice(0, 7).map((s) => <SubmissionMiniRow key={s.id} s={s} onOpen={() => go("detail", s.id)} />)}
          </Card>

          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <Card title="Team load">
              <div style={{
                display: "grid", gridTemplateColumns: "1fr 60px 110px 30px", gap: 10,
                fontSize: 10.5, fontWeight: 600, color: "var(--ink-4)",
                textTransform: "uppercase", letterSpacing: 0.5,
                paddingBottom: 4, borderBottom: "1px solid var(--border)"
              }}>
                <span>Team</span><span>Open</span><span>Capacity</span><span style={{ textAlign: "right" }}>Brh</span>
              </div>
              {SAMPLE.teamLoad.map((r) => <TeamLoadRow key={r.team} row={r} />)}
            </Card>

            <Card title="Compliance pulse" action={<span className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)" }}>30d</span>}>
              {SAMPLE.compliancePulse.map((c) => <ComplianceRow key={c.rule} {...c} />)}
            </Card>
          </div>
        </div>

        {/* Row: matter mix + ai usage */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14 }}>
          <Card title="Matter mix">
            <MatterMix />
          </Card>
          <Card title="AI co-pilot impact">
            <AiImpact />
          </Card>
          <Card title="Hash-chain audit">
            <AuditChainCard />
          </Card>
        </div>
      </div>
    </div>);

};

const ThroughputChart = ({ incoming, closed }) => {
  const w = 600,h = 130,pad = 22;
  const all = [...incoming, ...closed];
  const max = Math.max(...all);
  const stepX = (w - pad * 2) / (incoming.length - 1);
  const yFor = (v) => h - pad - v / max * (h - pad * 1.6);
  const path = (arr) => arr.map((v, i) => `${i === 0 ? "M" : "L"} ${(pad + i * stepX).toFixed(1)} ${yFor(v).toFixed(1)}`).join(" ");
  return (
    <div style={{ position: "relative" }}>
      <svg viewBox={`0 0 ${w} ${h}`} style={{ width: "100%", height: 140, display: "block" }}>
        {[0.25, 0.5, 0.75].map((g) =>
        <line key={g} x1={pad} x2={w - pad} y1={pad + g * (h - pad * 1.6)} y2={pad + g * (h - pad * 1.6)} stroke="var(--border)" strokeDasharray="2 3" />
        )}
        {/* incoming bars */}
        {incoming.map((v, i) =>
        <rect key={i}
        x={pad + i * stepX - 5}
        y={yFor(v)}
        width={10}
        height={h - pad - yFor(v)}
        fill="color-mix(in oklab, var(--primary) 18%, white)"
        rx={2} />

        )}
        {/* closed line */}
        <path d={path(closed)} stroke="var(--accent)" fill="none" strokeWidth={1.6} />
        {closed.map((v, i) =>
        <circle key={i} cx={pad + i * stepX} cy={yFor(v)} r={2.5} fill="var(--accent)" stroke="white" strokeWidth={1.2} />
        )}
        {/* x axis labels */}
        {incoming.map((_, i) => i % 2 === 0 &&
        <text key={i} x={pad + i * stepX} y={h - 5} textAnchor="middle" fontSize="9" fill="var(--ink-4)" className="mono">{`d-${incoming.length - 1 - i}`}</text>
        )}
      </svg>
    </div>);

};

const MatterMix = () => {
  const segments = [
  { label: "Litigation", pct: 28, color: "var(--primary)" },
  { label: "Land Use", pct: 22, color: "color-mix(in oklab, var(--primary) 60%, var(--accent))" },
  { label: "Contracts", pct: 19, color: "var(--accent)" },
  { label: "Public records", pct: 13, color: "var(--info)" },
  { label: "Code Enforce.", pct: 11, color: "var(--warning)" },
  { label: "Other", pct: 7, color: "var(--ink-4)" }];

  return (
    <div>
      <div style={{ display: "flex", height: 12, borderRadius: 6, overflow: "hidden", marginBottom: 12, boxShadow: "inset 0 0 0 1px var(--border)" }}>
        {segments.map((s) =>
        <div key={s.label} title={`${s.label} ${s.pct}%`} style={{ flex: s.pct, background: s.color }} />
        )}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "4px 14px" }}>
        {segments.map((s) =>
        <div key={s.label} style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 11.5 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: s.color }} />
            <span style={{ flex: 1, color: "var(--ink-2)" }}>{s.label}</span>
            <span className="num" style={{ fontWeight: 600, color: "var(--ink-2)" }}>{s.pct}%</span>
          </div>
        )}
      </div>
    </div>);

};

const AiImpact = () =>
<div style={{ display: "flex", gap: 14, alignItems: "center" }}>
    <Donut pct={71} size={70} stroke={8} color="var(--primary)" label={<span className="num">71<span style={{ fontSize: 9 }}>%</span></span>} />
    <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 7, fontSize: 11.5 }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span style={{ color: "var(--ink-3)" }}>Drafts assisted</span><span className="num" style={{ fontWeight: 600 }}>71%</span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span style={{ color: "var(--ink-3)" }}>Avg fields auto-filled</span><span className="num" style={{ fontWeight: 600 }}>4.2 / submit</span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span style={{ color: "var(--ink-3)" }}>Compliance saves</span><span className="num" style={{ fontWeight: 600, color: "var(--success)" }}>+38%</span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span style={{ color: "var(--ink-3)" }}>Median time-to-submit</span><span className="num" style={{ fontWeight: 600 }}>9 min</span>
      </div>
    </div>
  </div>;


const AuditChainCard = () =>
<div>
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
      <Pill tone="success" dot>Verified</Pill>
      <span style={{ fontSize: 11, color: "var(--ink-3)" }}>2 hours ago · 14,302 entries</span>
    </div>
    <div className="mono" style={{
    fontSize: 10.5, color: "var(--ink-3)", lineHeight: 1.6,
    background: "var(--muted)", padding: "8px 10px", borderRadius: 6,
    border: "1px solid var(--border)",
    overflow: "hidden"
  }}>
      <div><span style={{ color: "var(--ink-4)" }}>head</span> 4f9b…2a01</div>
      <div><span style={{ color: "var(--ink-4)" }}>prev</span> 2c8d…b71e</div>
      <div><span style={{ color: "var(--ink-4)" }}>algo</span> sha-256 · append-time</div>
      <div><span style={{ color: "var(--ink-4)" }}>next</span> auto-verify in 4h</div>
    </div>
    <Btn variant="default" size="sm" icon={<I.Shield size={12} />} style={{ marginTop: 10, width: "100%" }}>Verify chain now</Btn>
  </div>;


window.Dashboard = Dashboard;
window.PageHeader = PageHeader;