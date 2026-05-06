// sidebar — Notion/Linear style, dense
const { I } = window;

const NavItem = ({ icon, label, count, active, onClick, kbd, urgent }) => {
  const [hover, setHover] = React.useState(false);
  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        position: "relative",
        display: "flex", alignItems: "center", gap: 9,
        width: "100%", height: 28,
        padding: "0 9px", margin: 0,
        background: active ? "color-mix(in oklab, var(--sidebar-ink) 8%, transparent)" : (hover ? "color-mix(in oklab, var(--sidebar-ink) 5%, transparent)" : "transparent"),
        border: "none",
        borderRadius: 5,
        color: active ? "var(--sidebar-ink)" : "color-mix(in oklab, var(--sidebar-ink) 75%, transparent)",
        fontSize: 13,
        fontWeight: active ? 600 : 500,
        textAlign: "left",
        cursor: "pointer",
        transition: "background 80ms ease",
      }}
    >
      {active && (
        <span style={{
          position: "absolute", left: -10, top: 6, bottom: 6, width: 2.5,
          background: "var(--primary)", borderRadius: 4,
        }} />
      )}
      <span style={{ display: "flex", color: active ? "var(--primary)" : "color-mix(in oklab, var(--sidebar-ink) 65%, transparent)" }}>
        {icon}
      </span>
      <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{label}</span>
      {count !== undefined && (
        <span style={{
          fontSize: 10.5, fontWeight: 600,
          padding: "1px 6px", borderRadius: 999,
          background: urgent ? "color-mix(in oklab, var(--destructive) 18%, transparent)" : "color-mix(in oklab, var(--sidebar-ink) 8%, transparent)",
          color: urgent ? "var(--destructive)" : "color-mix(in oklab, var(--sidebar-ink) 70%, transparent)",
          minWidth: 18, textAlign: "center",
        }}>{count}</span>
      )}
      {kbd && (
        <span className="mono" style={{
          fontSize: 10, color: "color-mix(in oklab, var(--sidebar-ink) 50%, transparent)",
          padding: "1px 4px", border: "1px solid color-mix(in oklab, var(--sidebar-ink) 18%, transparent)",
          borderRadius: 3,
        }}>{kbd}</span>
      )}
    </button>
  );
};

const NavSection = ({ label, children, action }) => (
  <div style={{ display: "flex", flexDirection: "column", gap: 1, marginBottom: 14 }}>
    {label && (
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "0 10px",
        height: 22, marginBottom: 2,
      }}>
        <span style={{
          fontSize: 10.5, fontWeight: 600,
          color: "color-mix(in oklab, var(--sidebar-ink) 50%, transparent)",
          textTransform: "uppercase", letterSpacing: 0.6,
        }}>{label}</span>
        {action}
      </div>
    )}
    {children}
  </div>
);

const Sidebar = ({ route, setRoute, onNew }) => {
  return (
    <aside style={{
      width: 232, flex: "none",
      background: "var(--sidebar-bg)",
      color: "var(--sidebar-ink)",
      borderRight: "1px solid color-mix(in oklab, var(--sidebar-ink) 8%, transparent)",
      display: "flex", flexDirection: "column",
      padding: "10px 14px 12px",
      height: "100%",
    }}>
      {/* org switcher */}
      <button style={{
        display: "flex", alignItems: "center", gap: 9,
        height: 36, padding: "0 8px",
        background: "transparent", border: "none",
        borderRadius: 6, cursor: "pointer", marginBottom: 8,
      }}>
        <div style={{
          width: 24, height: 24, borderRadius: 5,
          background: "linear-gradient(135deg, var(--primary), color-mix(in oklab, var(--primary) 60%, var(--accent)))",
          color: "white", display: "grid", placeItems: "center",
          fontSize: 11, fontWeight: 700, letterSpacing: 0.4,
          boxShadow: "inset 0 -1px 0 rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,0.18)",
        }}>MC</div>
        <div style={{ display: "flex", flexDirection: "column", flex: 1, minWidth: 0, lineHeight: 1.15 }}>
          <span style={{ fontSize: 12.5, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>Manatee County</span>
          <span style={{ fontSize: 10.5, color: "color-mix(in oklab, var(--sidebar-ink) 55%, transparent)" }}>Legal · FY26</span>
        </div>
        <I.ChevronDown size={13} stroke={1.6} />
      </button>

      {/* search */}
      <div style={{
        display: "flex", alignItems: "center", gap: 7,
        height: 28, padding: "0 9px",
        background: "color-mix(in oklab, var(--sidebar-ink) 4%, transparent)",
        borderRadius: 5,
        marginBottom: 12,
        color: "color-mix(in oklab, var(--sidebar-ink) 60%, transparent)",
        fontSize: 12.5,
      }}>
        <I.Search size={13} />
        <span style={{ flex: 1 }}>Search RLS, people…</span>
        <span className="mono" style={{
          fontSize: 10, padding: "1px 4px",
          border: "1px solid color-mix(in oklab, var(--sidebar-ink) 16%, transparent)",
          borderRadius: 3,
        }}>⌘K</span>
      </div>

      {/* primary new-rls CTA */}
      <button onClick={onNew} style={{
        display: "flex", alignItems: "center", justifyContent: "center", gap: 7,
        height: 32, marginBottom: 14,
        background: "var(--primary)", color: "white",
        border: "none", borderRadius: 6,
        fontSize: 12.5, fontWeight: 600,
        cursor: "pointer", letterSpacing: 0.1,
        boxShadow: "inset 0 -1px 0 rgba(0,0,0,0.15), 0 1px 2px rgba(0,0,0,0.08)",
      }}>
        <I.Plus size={14} stroke={2} /> New RLS
        <span className="mono" style={{
          fontSize: 9.5, marginLeft: 4,
          padding: "1px 4px", borderRadius: 3,
          background: "rgba(255,255,255,0.18)",
        }}>N</span>
      </button>

      <div style={{ overflowY: "auto", flex: 1, marginRight: -8, paddingRight: 8 }}>
        <NavSection>
          <NavItem icon={<I.Dashboard size={15} />} label="Dashboard" active={route === "dashboard"} onClick={() => setRoute("dashboard")} kbd="G D" />
          <NavItem icon={<I.List size={15} />} label="Submissions" count={47} active={route === "submissions"} onClick={() => setRoute("submissions")} kbd="G S" />
          <NavItem icon={<I.Bell size={15} />} label="Inbox" count={3} urgent active={route === "inbox"} onClick={() => setRoute("inbox")} />
          <NavItem icon={<I.Doc size={15} />} label="Drafts" count={2} active={route === "drafts"} onClick={() => setRoute("drafts")} />
        </NavSection>

        <NavSection label="Workflows">
          <NavItem icon={<I.Building size={15} />} label="Code Enforcement" count={8} active={route === "ce"} onClick={() => setRoute("ce")} />
          <NavItem icon={<I.Scale size={15} />} label="BIE Worksheets" count={4} active={route === "bie"} onClick={() => setRoute("bie")} />
          <NavItem icon={<I.Map size={15} />} label="Land Use & Planning" count={11} active={route === "lu"} onClick={() => setRoute("lu")} />
          <NavItem icon={<I.Lock size={15} />} label="Public Records" count={6} active={route === "pr"} onClick={() => setRoute("pr")} />
        </NavSection>

        <NavSection label="Knowledge">
          <NavItem icon={<I.Robot size={15} />} label="AI Co-pilot" active={route === "ai"} onClick={() => setRoute("ai")} />
          <NavItem icon={<I.Graph size={15} />} label="Policy Graph" active={route === "policy"} onClick={() => setRoute("policy")} />
          <NavItem icon={<I.Library size={15} />} label="Precedents" active={route === "precedents"} onClick={() => setRoute("precedents")} />
          <NavItem icon={<I.Database size={15} />} label="KPI Analytics" active={route === "kpi"} onClick={() => setRoute("kpi")} />
        </NavSection>

        <NavSection label="Saved views">
          <NavItem icon={<I.Tag size={15} stroke={1.4} style={{ color: "var(--warning)" }} />} label="Breaching SLA" count={3} urgent />
          <NavItem icon={<I.Tag size={15} stroke={1.4} style={{ color: "var(--info)" }} />} label="Awaiting acknowledgment" count={6} />
          <NavItem icon={<I.Tag size={15} stroke={1.4} style={{ color: "var(--success)" }} />} label="My team" count={14} />
        </NavSection>
      </div>

      {/* footer */}
      <div style={{
        marginTop: 8, paddingTop: 10,
        borderTop: "1px solid color-mix(in oklab, var(--sidebar-ink) 8%, transparent)",
        display: "flex", alignItems: "center", gap: 9,
      }}>
        <div style={{
          width: 26, height: 26, borderRadius: 999,
          background: "linear-gradient(135deg, #8b6f47, #c89968)",
          color: "white", display: "grid", placeItems: "center",
          fontSize: 11, fontWeight: 600,
        }}>KT</div>
        <div style={{ flex: 1, minWidth: 0, lineHeight: 1.15 }}>
          <div style={{ fontSize: 12.5, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>Karen Tran</div>
          <div style={{ fontSize: 10.5, color: "color-mix(in oklab, var(--sidebar-ink) 55%, transparent)" }}>Senior Counsel · Litigation</div>
        </div>
        <I.Settings size={14} style={{ color: "color-mix(in oklab, var(--sidebar-ink) 55%, transparent)" }} />
      </div>
    </aside>
  );
};

window.Sidebar = Sidebar;
