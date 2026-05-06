// submissions list — dense, filterable, spreadsheet-like
const { I, UI, SAMPLE } = window;
const { Pill, StatusPill, UrgencyPill, Sparkline, Bar, Btn, Card, TextInput } = UI;
const { PageHeader } = window;

const FilterChip = ({ label, value, active, onClick }) => (
  <button onClick={onClick} style={{
    display: "inline-flex", alignItems: "center", gap: 5,
    height: 26, padding: "0 9px",
    background: active ? "color-mix(in oklab, var(--primary) 12%, white)" : "var(--canvas)",
    border: `1px solid ${active ? "color-mix(in oklab, var(--primary) 30%, white)" : "var(--border-strong)"}`,
    borderRadius: 5,
    fontSize: 11.5, fontWeight: 500,
    color: active ? "var(--primary-ink)" : "var(--ink-2)",
    cursor: "pointer", whiteSpace: "nowrap",
  }}>
    <span>{label}</span>
    {value !== undefined && <span style={{ color: active ? "var(--primary-ink)" : "var(--ink-3)" }}>{value}</span>}
    <I.ChevronDown size={11} stroke={1.4} />
  </button>
);

const RiskDot = ({ risk }) => {
  const colors = { Low: "var(--success)", Medium: "var(--warning)", High: "var(--destructive)", "—": "var(--ink-4)" };
  return <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
    <span style={{ width: 6, height: 6, borderRadius: 999, background: colors[risk] }} />
    <span style={{ color: risk === "—" ? "var(--ink-4)" : "var(--ink-2)" }}>{risk}</span>
  </span>;
};

const Avatar = ({ name, size = 20 }) => {
  if (name === "—") return <span style={{ color: "var(--ink-4)", fontSize: 11 }}>—</span>;
  const initials = name.split(/\s+/).map(p => p[0]).slice(0, 2).join("");
  const hash = [...name].reduce((a, c) => a + c.charCodeAt(0), 0);
  const hues = [200, 28, 145, 250, 320, 70];
  const h = hues[hash % hues.length];
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span style={{
        width: size, height: size, borderRadius: 999,
        background: `oklch(0.7 0.1 ${h})`,
        color: "white", fontSize: size <= 20 ? 9.5 : 11, fontWeight: 600,
        display: "grid", placeItems: "center",
        boxShadow: "inset 0 -1px 0 rgba(0,0,0,0.12)",
      }}>{initials}</span>
      <span>{name}</span>
    </span>
  );
};

const HeaderCell = ({ children, w, align = "left" }) => (
  <div style={{
    fontSize: 10.5, fontWeight: 600, color: "var(--ink-3)",
    textTransform: "uppercase", letterSpacing: 0.5,
    padding: "8px 10px", textAlign: align,
    width: w, flex: w ? "none" : 1, minWidth: 0,
    borderRight: "1px solid var(--border)",
  }}>{children}</div>
);

const Cell = ({ children, w, align = "left", style, mono }) => (
  <div style={{
    fontSize: 12, color: "var(--ink-2)",
    padding: "0 10px", textAlign: align,
    width: w, flex: w ? "none" : 1, minWidth: 0,
    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
    fontFamily: mono ? "var(--mono)" : "inherit",
    fontVariantNumeric: "tabular-nums",
    display: "flex", alignItems: "center",
    ...style,
  }}>{children}</div>
);

const Submissions = ({ go, lens }) => {
  // SAMPLE.submissions is the first-paint fallback; live data from the
  // gateway lands in `items` once /api/rls resolves. On Pages (no
  // gateway) the component stays on SAMPLE — fetch fails silently.
  const [items, setItems] = React.useState(SAMPLE.submissions);
  React.useEffect(() => {
    if (!window.RLS_API) return;
    let alive = true;
    window.RLS_API.rls.list()
      .then(r => { if (alive && r && r.items) setItems(r.items); })
      .catch(() => {});
    return () => { alive = false; };
  }, []);

  const [q, setQ] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState("all");
  // `lens` lets parent routes scope the same Submissions list to a slice
  // (e.g. team="Land Use" or type="Public Records") without forking the
  // component. Lens fields applied first; status/q filter on top.
  const lensed = items.filter(s => {
    if (!lens || !lens.match) return true;
    return lens.match(s);
  });
  const filtered = lensed.filter(s => {
    if (statusFilter !== "all" && s.status.toLowerCase() !== statusFilter) return false;
    if (q && !(`${s.id} ${s.title} ${s.requester}`.toLowerCase().includes(q.toLowerCase()))) return false;
    return true;
  });

  const counts = lensed.reduce((m, s) => { m[s.status] = (m[s.status] || 0) + 1; return m; }, {});

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden" }}>
      <PageHeader
        title={(lens && lens.title) || "Submissions"}
        sub={(lens && lens.sub) || `${items.length} matters · sorted by deadline · grouped by team`}
        right={
          <>
            <Btn icon={<I.Eye size={13} />} variant="default" size="sm">View</Btn>
            <Btn icon={<I.Branch size={13} />} variant="default" size="sm">Group</Btn>
            <Btn icon={<I.Plus size={13} stroke={2} />} variant="primary" size="sm" onClick={() => go("wizard")}>New RLS</Btn>
          </>
        }
      />

      {/* status tabs */}
      <div style={{ display: "flex", gap: 0, padding: "0 20px", borderBottom: "1px solid var(--border)", background: "var(--bg)" }}>
        {[
          { id: "all", label: "All", n: lensed.length },
          { id: "draft", label: "Draft", n: counts.Draft || 0 },
          { id: "submitted", label: "Submitted", n: counts.Submitted || 0 },
          { id: "acknowledged", label: "Acknowledged", n: counts.Acknowledged || 0 },
          { id: "assigned", label: "Assigned", n: counts.Assigned || 0 },
          { id: "complete", label: "Complete", n: counts.Complete || 0 },
          { id: "rejected", label: "Rejected", n: counts.Rejected || 0 },
        ].map(t => (
          <button key={t.id} onClick={() => setStatusFilter(t.id)} style={{
            background: "none", border: "none",
            padding: "10px 12px", marginRight: 4,
            fontSize: 12.5, fontWeight: statusFilter === t.id ? 600 : 500,
            color: statusFilter === t.id ? "var(--ink)" : "var(--ink-3)",
            borderBottom: `2px solid ${statusFilter === t.id ? "var(--primary)" : "transparent"}`,
            cursor: "pointer", display: "flex", alignItems: "center", gap: 6,
          }}>
            {t.label}
            <span style={{
              fontSize: 10.5, padding: "0 5px", borderRadius: 999,
              background: statusFilter === t.id ? "color-mix(in oklab, var(--primary) 14%, white)" : "var(--muted-2)",
              color: statusFilter === t.id ? "var(--primary-ink)" : "var(--ink-3)",
              fontWeight: 600,
            }}>{t.n}</span>
          </button>
        ))}
      </div>

      {/* filter bar */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 20px", borderBottom: "1px solid var(--border)", background: "var(--canvas)" }}>
        <TextInput
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search by ID, title, requester…"
          prefix={<I.Search size={13} style={{ color: "var(--ink-3)" }} />}
          suffix={<span className="mono" style={{ fontSize: 10, padding: "1px 4px", border: "1px solid var(--border)", borderRadius: 3, color: "var(--ink-4)" }}>/</span>}
          style={{ width: 320, height: 30 }}
        />
        <span style={{ width: 1, height: 18, background: "var(--border)" }} />
        <FilterChip label="Team" value="all" />
        <FilterChip label="Urgency" value="all" />
        <FilterChip label="Risk" value="all" />
        <FilterChip label="Department" value="all" />
        <FilterChip label="Has BIE" />
        <FilterChip label="Deadline" value="this week" active />
        <span style={{ flex: 1 }} />
        <Btn variant="ghost" size="sm" icon={<I.Plus size={12} />}>Add filter</Btn>
        <Btn variant="default" size="sm" icon={<I.Copy size={12} />}>Export</Btn>
      </div>

      {/* table */}
      <div style={{ flex: 1, overflow: "auto", background: "var(--canvas)" }}>
        <div style={{
          display: "flex", alignItems: "stretch",
          background: "var(--muted)",
          borderBottom: "1px solid var(--border)",
          position: "sticky", top: 0, zIndex: 1,
        }}>
          <HeaderCell w={104}>ID</HeaderCell>
          <HeaderCell>Matter</HeaderCell>
          <HeaderCell w={110}>Type</HeaderCell>
          <HeaderCell w={120}>Status</HeaderCell>
          <HeaderCell w={80}>Urgency</HeaderCell>
          <HeaderCell w={120}>Assignee</HeaderCell>
          <HeaderCell w={120}>Team</HeaderCell>
          <HeaderCell w={84} align="right">Risk</HeaderCell>
          <HeaderCell w={92} align="right">Compl.</HeaderCell>
          <HeaderCell w={88} align="right">Deadline</HeaderCell>
          <HeaderCell w={110} style={{ borderRight: "none" }}>Activity 14d</HeaderCell>
        </div>

        {filtered.map((s, idx) => (
          <SubmissionRow key={s.id} s={s} onOpen={() => go("detail", s.id)} alt={idx % 2 === 1} />
        ))}
      </div>

      <div style={{ height: 32, padding: "0 20px", display: "flex", alignItems: "center", justifyContent: "space-between", borderTop: "1px solid var(--border)", fontSize: 11, color: "var(--ink-3)", background: "var(--canvas)" }}>
        <span>{filtered.length} of {lensed.length} matters · 3 breaching · 6 awaiting acknowledgment</span>
        <span className="mono">↑ ↓ to navigate · Enter to open · ⌘N for new</span>
      </div>
    </div>
  );
};

const SubmissionRow = ({ s, onOpen, alt }) => {
  const dl = s.workingDays;
  const dlTone = dl < 0 ? "var(--destructive)" : dl <= 2 ? "var(--warning)" : "var(--ink-2)";
  return (
    <div onClick={onOpen} style={{
      display: "flex", alignItems: "stretch",
      borderBottom: "1px solid var(--border)",
      background: alt ? "color-mix(in oklab, var(--muted) 35%, white)" : "var(--canvas)",
      height: 38, cursor: "pointer",
      transition: "background 80ms ease",
    }} onMouseEnter={(e) => e.currentTarget.style.background = "color-mix(in oklab, var(--primary) 4%, white)"}
       onMouseLeave={(e) => e.currentTarget.style.background = alt ? "color-mix(in oklab, var(--muted) 35%, white)" : "var(--canvas)"}>
      <Cell w={104} mono style={{ fontWeight: 600, color: "var(--ink-2)" }}>{s.id}</Cell>
      <Cell>
        <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
          <I.Doc size={12} style={{ color: "var(--ink-4)", flex: "none" }} />
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", color: "var(--ink)", fontWeight: 500 }}>{s.title}</span>
          {s.bie && <Pill tone="warning" style={{ padding: "0 5px", fontSize: 9.5 }}>BIE</Pill>}
          {s.attachments > 0 && (
            <span style={{ display: "inline-flex", alignItems: "center", gap: 2, color: "var(--ink-4)", fontSize: 11 }}>
              <I.Paperclip size={11} />{s.attachments}
            </span>
          )}
        </div>
      </Cell>
      <Cell w={110}><Pill tone="ghost" style={{ border: "1px solid var(--border)" }}>{s.type}</Pill></Cell>
      <Cell w={120}><StatusPill status={s.status} /></Cell>
      <Cell w={80}><UrgencyPill urgency={s.urgency} /></Cell>
      <Cell w={120}><Avatar name={s.assignee} /></Cell>
      <Cell w={120} style={{ color: "var(--ink-3)" }}>{s.team}</Cell>
      <Cell w={84} align="right" style={{ justifyContent: "flex-end" }}>
        <RiskDot risk={s.risk} />
      </Cell>
      <Cell w={92} align="right" style={{ justifyContent: "flex-end", gap: 6 }}>
        <Bar pct={s.completeness} h={3} style={{ width: 38 }} color={s.completeness >= 90 ? "var(--success)" : s.completeness >= 60 ? "var(--warning)" : "var(--destructive)"} />
        <span className="num" style={{ fontWeight: 600, fontSize: 11.5, color: "var(--ink-2)" }}>{s.completeness}%</span>
      </Cell>
      <Cell w={88} align="right" style={{ justifyContent: "flex-end", color: dlTone, fontWeight: 600 }} mono>
        {dl < 0 ? `${dl}d` : dl === 0 ? "today" : `+${dl}d`}
      </Cell>
      <Cell w={110} style={{ color: "var(--primary)", borderRight: "none" }}>
        <Sparkline data={s.activity} w={94} h={20} stroke="currentColor" fill="color-mix(in oklab, currentColor 14%, transparent)" />
      </Cell>
    </div>
  );
};

window.Submissions = Submissions;
