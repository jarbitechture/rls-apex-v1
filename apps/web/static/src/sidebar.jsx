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

const Sidebar = ({ route, setRoute, onNew, user }) => {
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
      {/* org plate — display-only, not clickable. The dropdown affordance
          was removed since there's only one org and no menu to show. */}
      <div style={{
        display: "flex", alignItems: "center", gap: 9,
        height: 36, padding: "0 8px", marginBottom: 12,
      }}>
        <div style={{
          width: 24, height: 24, borderRadius: 5,
          background: "linear-gradient(135deg, var(--primary), color-mix(in oklab, var(--primary) 60%, var(--accent)))",
          color: "white", display: "grid", placeItems: "center",
          fontSize: 11, fontWeight: 700, letterSpacing: 0.4,
          boxShadow: "inset 0 -1px 0 rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,0.18)",
        }}>MC</div>
        <div style={{ display: "flex", flexDirection: "column", flex: 1, minWidth: 0, lineHeight: 1.15 }}>
          <span style={{ fontSize: 13, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>Manatee County</span>
          <span style={{ fontSize: 11, color: "color-mix(in oklab, var(--sidebar-ink) 55%, transparent)" }}>RLS Apex · v0.1.0</span>
        </div>
      </div>

      {/* primary CTA — routes to Validate (the pilot's flow) */}
      <button onClick={() => setRoute("ai")} style={{
        display: "flex", alignItems: "center", justifyContent: "center", gap: 7,
        height: 32, marginBottom: 14,
        background: "var(--primary)", color: "white",
        border: "none", borderRadius: 6,
        fontSize: 12.5, fontWeight: 600,
        cursor: "pointer", letterSpacing: 0.1,
        boxShadow: "inset 0 -1px 0 rgba(0,0,0,0.15), 0 1px 2px rgba(0,0,0,0.08)",
      }}>
        <I.Plus size={14} stroke={2} /> Validate a draft
      </button>

      <div style={{ overflowY: "auto", flex: 1, marginRight: -8, paddingRight: 8 }}>
        {/* v0.1.0 ships only the routes backed by real wiring. Mock-data
            surfaces (Dashboard, Submissions, Inbox, Drafts, Workflows,
            Saved views) are intentionally hidden until they have backing
            data — they were misleading the pilot's stated maturity. */}
        <NavSection>
          <NavItem icon={<I.Robot size={15} />} label="Validate" active={route === "ai"} onClick={() => setRoute("ai")} />
          <NavItem icon={<I.Folder size={15} />} label="Documents" active={route === "documents"} onClick={() => setRoute("documents")} />
          {/* Precedents hidden — Validate's citation block already surfaces
              the same /api/retrieve hits, so a standalone Precedents library
              page would just duplicate. Restore once it has a different
              shape (e.g., editorial collections). */}
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
        }}>{(user && user.initials) || "RP"}</div>
        <div style={{ flex: 1, minWidth: 0, lineHeight: 1.15 }}>
          <div style={{ fontSize: 12.5, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{(user && user.display_name) || "RLS Pilot"}</div>
          <div style={{ fontSize: 10.5, color: "color-mix(in oklab, var(--sidebar-ink) 55%, transparent)" }}>{(user && user.role) || "v0.1.0 · mock"}</div>
        </div>
        {/* Settings gear removed — no settings surface in v0.1.0. */}
      </div>
    </aside>
  );
};

window.Sidebar = Sidebar;
