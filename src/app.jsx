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
  const [route, setRoute] = React.useState("dashboard");
  const [detailId, setDetailId] = React.useState(null);

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
    if (route === "ai") return <window.AiPage go={go} />;
    if (route === "bie") return <window.Bie go={go} />;
    if (route === "ce") return <window.CodeEnforcement go={go} />;
    if (route === "lu") return <Submissions go={go} />;
    if (route === "pr") return <Submissions go={go} />;
    if (route === "policy") return <window.Policy />;
    if (route === "precedents") return <window.Precedents go={go} />;
    if (route === "kpi") return <window.Kpi />;
    return <StubPage route={route} go={go} />;
  })();

  return (
    <div style={{ display: "flex", height: "100%", width: "100%" }}>
      <Sidebar route={route} setRoute={(r) => { setRoute(r); }} onNew={() => go("wizard")} />
      <main style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", background: "var(--bg)" }}>
        {page}
      </main>
      <TweaksPanel>
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
      </TweaksPanel>
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
