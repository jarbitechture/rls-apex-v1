// app shell — composes everything
const { Sidebar, Dashboard, Submissions, Wizard, Detail, I, UI } = window;
const { useTweaks, TweaksPanel, TweakSection, TweakRadio, TweakColor, TweakSelect } = window;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "primary": "#2B7A9E",
  "sidebar": "warm",
  "card": "soft",
  "page": "dashboard"
}/*EDITMODE-END*/;

function App() {
  const [tweaks, setTweak] = useTweaks(TWEAK_DEFAULTS);
  // Default landing = Validate (route "ai"). Per the pilot's actual purpose:
  // user pastes a draft RLS, gets a pre-submission check. Dashboard is one
  // click away in the sidebar but no longer the entry point.
  const [route, setRoute] = React.useState("ai");
  const [detailId, setDetailId] = React.useState(null);

  // Auth state. `loading` while /api/me is in flight, then either a real
  // user (200) or a 403 (allowlist denial). Tracked via React state so the
  // sidebar footer + auth wall actually re-render when the fetch resolves.
  const [user, setUser] = React.useState(null);
  const [authState, setAuthState] = React.useState("loading"); // loading | allowed | denied | offline
  React.useEffect(() => {
    if (!window.RLS_API) { setAuthState("offline"); return; }
    window.RLS_API.get("/api/me")
      .then(u => { setUser(u); setAuthState("allowed"); })
      .catch(e => {
        if (e && e.status === 403) setAuthState("denied");
        else setAuthState("offline");
      });
  }, []);

  // Dev hook: expose route + detail navigation only when explicitly running
  // UI-simplicity / verification checks. No-op in prod.
  React.useEffect(() => {
    if (window.__RLS_TEST || /\bui_simplicity=1\b/.test(window.location.search)) {
      window.__RLS_ROUTE_SET = setRoute;
      window.__RLS_DETAIL_SET = setDetailId;
      window.__RLS_GO = (r, id) => { if (id) setDetailId(id); setRoute(r); };
    }
  }, [setRoute, setDetailId]);

  React.useEffect(() => {
    document.body.dataset.sidebar = tweaks.sidebar;
    document.body.dataset.card = tweaks.card;
    document.documentElement.style.setProperty("--primary", tweaks.primary);
  }, [tweaks]);

  const go = (r, id) => {
    if (id) setDetailId(id);
    setRoute(r);
  };

  const page = (() => {
    if (route === "dashboard") return <Dashboard go={go} />;
    if (route === "submissions") return <Submissions go={go} />;
    if (route === "wizard") return <Wizard go={go} />;
    if (route === "detail") return <Detail id={detailId} go={go} />;
    if (route === "inbox") return <window.Inbox go={go} />;
    if (route === "drafts") return <window.Drafts go={go} />;
    if (route === "documents") return <window.Documents go={go} />;
    if (route === "ai") return <window.AiPage go={go} />;
    if (route === "bie") return <window.Bie go={go} />;
    if (route === "ce") return <window.CodeEnforcement go={go} />;
    if (route === "lu") return <Submissions go={go} lens={{
      title: "Land Use & Planning",
      sub: "Submissions routed to the Land Use team",
      match: (s) => s.team === "Land Use" || s.matter === "Drafting" && s.type === "Ordinance",
    }} />;
    if (route === "pr") return <Submissions go={go} lens={{
      title: "Public Records",
      sub: "Chapter 119 requests and policy guidance",
      match: (s) => s.type === "Public Records" || s.department === "Sheriff",
    }} />;
    if (route === "policy") return <window.Policy />;
    if (route === "precedents") return <window.Precedents go={go} />;
    if (route === "kpi") return <window.Kpi />;
    return <StubPage route={route} go={go} />;
  })();

  // Auth wall. Renders before the app surface when the gateway returns 403
  // (allowlist denial). 'offline' = Pages or no gateway — degrade
  // gracefully and let the static prototype render unauthenticated.
  if (authState === "denied") {
    return (
      <div style={{ display: "grid", placeItems: "center", height: "100%", width: "100%", background: "var(--bg)" }}>
        <div style={{ maxWidth: 460, padding: 32, background: "var(--canvas)", border: "1px solid var(--border)", borderRadius: 12, textAlign: "center" }}>
          <div style={{ width: 44, height: 44, borderRadius: 22, background: "color-mix(in oklab, var(--destructive) 15%, white)", color: "var(--destructive)", margin: "0 auto 12px", display: "grid", placeItems: "center" }}>🔒</div>
          <div className="serif" style={{ fontSize: 20, fontWeight: 600, marginBottom: 6 }}>Access denied</div>
          <p style={{ fontSize: 13.5, color: "var(--ink-2)", lineHeight: 1.55, margin: 0 }}>
            This account is not on the RLS Apex v1 allowlist. Contact the IT/Legal owner if you should have access.
          </p>
          <div className="mono" style={{ marginTop: 18, fontSize: 11, color: "var(--ink-3)" }}>
            RLS_ALLOWLIST gate · /api/me 403
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", height: "100%", width: "100%" }}>
      <Sidebar route={route} setRoute={(r) => { setRoute(r); }} onNew={() => go("wizard")} user={user} />
      <main style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", background: "var(--bg)" }}>
        {page}
      </main>
      {/* TweaksPanel — dev-only design-token tinkerer. Gated behind
          ?tweaks=1 so the production view doesn't render the floating
          edge-tab. */}
      {/\btweaks=1\b/.test(window.location.search) && <TweaksPanel>
        <TweakSection label="Primary accent" />
        <TweakColor label="Color" value={tweaks.primary} onChange={(v) => setTweak("primary", v)} />

        <TweakSection label="Sidebar tone" />
        <TweakRadio label="Tone" value={tweaks.sidebar}
          options={["warm", "cool", "ink", "dark"]}
          onChange={(v) => setTweak("sidebar", v)} />

        <TweakSection label="Card style" />
        <TweakRadio label="Cards" value={tweaks.card}
          options={["soft", "flat", "lift"]}
          onChange={(v) => setTweak("card", v)} />

        <TweakSection label="Jump to page" />
        <TweakSelect label="Page" value={route}
          options={[
            { value: "dashboard", label: "Dashboard" },
            { value: "submissions", label: "Submissions" },
            { value: "wizard", label: "New RLS wizard" },
            { value: "detail", label: "RLS detail" },
          ]}
          onChange={(v) => { if (v === "detail") setDetailId("RLS-26-0141"); setRoute(v); }} />
      </TweaksPanel>}
    </div>
  );
}

function StubPage({ route, go }) {
  const labels = {
    inbox: "Inbox", drafts: "Drafts",
    ce: "Code Enforcement", bie: "BIE Worksheets", lu: "Land Use & Planning", pr: "Public Records",
    ai: "AI Co-pilot", policy: "Policy Graph", precedents: "Precedents", kpi: "KPI Analytics",
  };
  return (
    <div style={{ flex: 1, display: "grid", placeItems: "center", padding: 40 }}>
      <div style={{ textAlign: "center", maxWidth: 380 }}>
        <I.Sparkles size={28} style={{ color: "var(--ink-4)" }} />
        <h2 style={{ fontSize: 17, fontWeight: 600, margin: "10px 0 4px" }}>{labels[route] || route}</h2>
        <p style={{ fontSize: 12.5, color: "var(--ink-3)", marginBottom: 16, lineHeight: 1.5 }}>
          Stub view — main flow is Dashboard → Submissions → New RLS Wizard → Detail. Use the Tweaks panel to jump between primary screens.
        </p>
        <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
          <UI.Btn variant="primary" size="sm" onClick={() => go("dashboard")}>Back to dashboard</UI.Btn>
          <UI.Btn variant="default" size="sm" onClick={() => go("wizard")}>Start new RLS</UI.Btn>
        </div>
      </div>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
