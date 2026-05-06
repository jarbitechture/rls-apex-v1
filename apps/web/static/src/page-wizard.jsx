// 3-pane wizard: timeline (compliance graph) | intake form (with inline AI signals) | live preview
const { I, UI, SAMPLE } = window;
const { Pill, StatusPill, UrgencyPill, Bar, Btn, Card, Donut, Field, TextInput } = UI;
const { PageHeader } = window;

// === Inline AI signal that sits inside form fields ===
const AISignal = ({ tone = "info", icon, children, action }) => {
  const colors = {
    info:    { bg: "color-mix(in oklab, var(--primary) 8%, white)",  fg: "var(--primary-ink)", bd: "color-mix(in oklab, var(--primary) 22%, white)" },
    warning: { bg: "color-mix(in oklab, var(--warning) 10%, white)", fg: "var(--warning)",     bd: "color-mix(in oklab, var(--warning) 25%, white)" },
    success: { bg: "color-mix(in oklab, var(--success) 10%, white)", fg: "var(--success)",     bd: "color-mix(in oklab, var(--success) 25%, white)" },
    danger:  { bg: "color-mix(in oklab, var(--destructive) 10%, white)", fg: "var(--destructive)", bd: "color-mix(in oklab, var(--destructive) 25%, white)" },
  };
  const c = colors[tone];
  return (
    <div style={{
      marginTop: 6, padding: "6px 9px",
      background: c.bg, border: `1px solid ${c.bd}`, borderRadius: 6,
      display: "flex", gap: 7, alignItems: "flex-start",
      fontSize: 11.5, color: c.fg, lineHeight: 1.45,
    }}>
      <span style={{ display: "flex", marginTop: 1 }}>{icon || <I.Sparkles size={12} />}</span>
      <div style={{ flex: 1, minWidth: 0 }}>{children}</div>
      {action && <button style={{ background: "transparent", border: "none", color: c.fg, fontWeight: 600, fontSize: 11, padding: 0, cursor: "pointer", textDecoration: "underline" }} onClick={action.onClick}>{action.label}</button>}
    </div>
  );
};

// === Compliance timeline (left pane) — living graph ===
const TimelineNode = ({ idx, label, sub, status, active, onClick }) => {
  const colors = {
    done: { bg: "var(--success)", ring: "color-mix(in oklab, var(--success) 25%, white)" },
    active: { bg: "var(--primary)", ring: "color-mix(in oklab, var(--primary) 25%, white)" },
    warn: { bg: "var(--warning)", ring: "color-mix(in oklab, var(--warning) 22%, white)" },
    pending: { bg: "var(--canvas)", ring: "var(--border-strong)" },
  };
  const c = colors[status];
  return (
    <button onClick={onClick} style={{
      display: "grid", gridTemplateColumns: "26px 1fr", gap: 10,
      padding: "8px 10px", margin: 0, background: active ? "color-mix(in oklab, var(--primary) 6%, white)" : "transparent",
      border: "none", borderRadius: 6, textAlign: "left", cursor: "pointer", width: "100%",
      transition: "background 100ms",
    }}>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", paddingTop: 3 }}>
        <span style={{
          width: 18, height: 18, borderRadius: 999,
          background: c.bg, color: "white",
          display: "grid", placeItems: "center",
          fontSize: 10, fontWeight: 700,
          border: status === "pending" ? "1.5px solid var(--border-strong)" : "none",
          boxShadow: active ? `0 0 0 4px ${c.ring}` : "none",
          transition: "box-shadow 200ms",
        }}>
          {status === "done" ? <I.Check size={11} stroke={2.5} /> : status === "warn" ? <I.Alert size={10} stroke={2} /> : <span style={{ color: status === "pending" ? "var(--ink-3)" : "white" }}>{idx}</span>}
        </span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.3, minWidth: 0 }}>
        <span style={{ fontSize: 12.5, fontWeight: active ? 600 : 500, color: status === "pending" ? "var(--ink-3)" : "var(--ink)" }}>{label}</span>
        {sub && <span style={{ fontSize: 10.5, color: "var(--ink-3)" }}>{sub}</span>}
      </div>
    </button>
  );
};

const ComplianceGraph = ({ step, completeness, draft }) => {
  // 8 compliance "lanes" — light up as draft progresses
  const lanes = [
    { id: "subj", label: "Subject ≤ 50 chars", check: () => draft.title.length > 0 && draft.title.length <= 50, val: () => `${draft.title.length}/50` },
    { id: "qlen", label: "Question ≤ 2000 chars", check: () => draft.question.length > 0 && draft.question.length <= 2000, val: () => `${draft.question.length}/2000` },
    { id: "indiv", label: "Individual attachments", check: () => draft.attachments.every(a => !a.combined), val: () => `${draft.attachments.length} files` },
    { id: "wordfmt", label: "Word for draft contracts", check: () => draft.matterType !== "Contract" || draft.attachments.some(a => /\.docx?$/i.test(a.name)), val: () => "—" },
    { id: "bie", label: "BIE for proposed ordinance", check: () => draft.matterType !== "Ordinance" || draft.bieFiled, val: () => draft.bieFiled ? "filed" : "needed" },
    { id: "dirsig", label: "Director signature (urgent)", check: () => !["Urgent","Critical"].includes(draft.urgency) || draft.directorSig, val: () => draft.directorSig ? "signed" : "—" },
    { id: "noemail", label: "No substantive email body", check: () => true, val: () => "auto" },
    { id: "prflag", label: "Public-records flag valid", check: () => true, val: () => "ok" },
  ];

  return (
    <div>
      <div style={{ padding: "0 12px 12px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
          <Donut pct={completeness} size={56} stroke={6} color={completeness >= 90 ? "var(--success)" : completeness >= 60 ? "var(--primary)" : "var(--warning)"} label={<span className="num" style={{ fontSize: 13, fontWeight: 700 }}>{completeness}<span style={{ fontSize: 8 }}>%</span></span>} />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink)" }}>Completeness</div>
            <div style={{ fontSize: 11, color: "var(--ink-3)" }}>
              {completeness >= 90 ? "Ready to submit" : completeness >= 60 ? "Almost there" : "Keep filling"}
            </div>
          </div>
        </div>
      </div>

      <div style={{ padding: "10px 6px", borderBottom: "1px solid var(--border)" }}>
        <div style={{ fontSize: 10.5, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.6, color: "var(--ink-3)", padding: "0 10px 6px" }}>Steps</div>
        {[
          { idx: 1, label: "Matter type", sub: draft.matterType || "Choose category", status: step > 0 ? "done" : "active" },
          { idx: 2, label: "Question", sub: draft.title ? `“${draft.title.slice(0, 24)}…”` : "Subject + body", status: step > 1 ? "done" : step === 1 ? "active" : "pending" },
          { idx: 3, label: "Routing & deadline", sub: draft.team || "Suggested by AI", status: step > 2 ? "done" : step === 2 ? "active" : "pending" },
          { idx: 4, label: "Attachments", sub: `${draft.attachments.length} files`, status: step > 3 ? "done" : step === 3 ? "active" : draft.attachments.some(a => a.combined) ? "warn" : "pending" },
          { idx: 5, label: "Review & submit", sub: "Hash-chain entry", status: step === 4 ? "active" : "pending" },
        ].map((s, i) => (
          <TimelineNode key={s.idx} {...s} active={step === i} />
        ))}
      </div>

      <div style={{ padding: "10px 14px" }}>
        <div style={{ fontSize: 10.5, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.6, color: "var(--ink-3)", marginBottom: 8 }}>
          Compliance lanes <span style={{ float: "right", color: "var(--ink-4)", letterSpacing: 0 }}>live</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {lanes.map(lane => {
            const passed = lane.check();
            return (
              <div key={lane.id} style={{
                display: "grid", gridTemplateColumns: "10px 1fr auto", gap: 8, alignItems: "center",
                padding: "5px 6px", borderRadius: 4,
                background: passed ? "transparent" : "color-mix(in oklab, var(--warning) 5%, transparent)",
                fontSize: 11.5,
              }}>
                <span style={{
                  width: 8, height: 8, borderRadius: 999,
                  background: passed ? "var(--success)" : "var(--warning)",
                  boxShadow: passed ? "0 0 0 2px color-mix(in oklab, var(--success) 22%, transparent)" : "0 0 0 2px color-mix(in oklab, var(--warning) 22%, transparent)",
                }} />
                <span style={{ color: passed ? "var(--ink-2)" : "var(--ink)", fontWeight: passed ? 400 : 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{lane.label}</span>
                <span className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)" }}>{lane.val()}</span>
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ padding: "10px 14px", borderTop: "1px solid var(--border)", marginTop: 8 }}>
        <div style={{ fontSize: 10.5, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.6, color: "var(--ink-3)", marginBottom: 6 }}>Working days</div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
          <span className="num" style={{ fontSize: 22, fontWeight: 600, letterSpacing: -0.4 }}>10</span>
          <span style={{ fontSize: 11, color: "var(--ink-3)" }}>days to deadline · May 19</span>
        </div>
        <div style={{ fontSize: 10.5, color: "var(--ink-4)", marginTop: 4 }}>excludes weekends + 1 county holiday (Memorial Day)</div>
      </div>
    </div>
  );
};

// === MIDDLE: intake form ===
const MatterTypeCard = ({ id, icon, title, desc, hint, selected, onClick, badge }) => (
  <button onClick={onClick} style={{
    display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 8,
    padding: 14, textAlign: "left", width: "100%",
    background: selected ? "color-mix(in oklab, var(--primary) 7%, white)" : "var(--canvas)",
    border: `1.5px solid ${selected ? "var(--primary)" : "var(--border)"}`,
    borderRadius: 8, cursor: "pointer",
    boxShadow: selected ? "0 0 0 4px color-mix(in oklab, var(--primary) 12%, transparent)" : "none",
    transition: "all 120ms",
    minHeight: 110,
  }}>
    <div style={{ display: "flex", alignItems: "center", gap: 8, width: "100%" }}>
      <div style={{
        width: 28, height: 28, borderRadius: 6,
        background: selected ? "var(--primary)" : "var(--muted)",
        color: selected ? "white" : "var(--ink-2)",
        display: "grid", placeItems: "center",
      }}>{icon}</div>
      <div style={{ fontSize: 13, fontWeight: 600, flex: 1, color: "var(--ink)" }}>{title}</div>
      {badge}
    </div>
    <div style={{ fontSize: 11.5, color: "var(--ink-3)", lineHeight: 1.4 }}>{desc}</div>
    {hint && <div style={{ fontSize: 10.5, color: "var(--primary-ink)", display: "inline-flex", alignItems: "center", gap: 4 }}><I.Sparkles size={10} />{hint}</div>}
  </button>
);

const Wizard = ({ go }) => {
  const [step, setStep] = React.useState(1);
  const [draft, setDraft] = React.useState({
    matterType: "Ordinance",
    urgency: "Critical",
    title: "Short-term rental amendment §125.66(3)(c)",
    question: "Council requests a legal sufficiency review of the proposed amendment to the short-term rental ordinance. The amendment introduces a 7-night minimum stay in coastal residential zones, an annual permit fee tied to occupancy load, and adds a private right of action for adjacent property owners. We need confirmation that the private right of action is constitutionally permissible under Florida home-rule preemption and that the BIE is properly noticed.",
    department: "Planning & Zoning",
    requester: "Sasha Lin",
    team: "",
    deadline: "2026-05-18",
    bieFiled: false,
    directorSig: false,
    publicRecord: false,
    attachments: [
      { name: "draft-ordinance-v3.docx", combined: false, size: "84 KB" },
      { name: "BIE-worksheet-v2.pdf", combined: false, size: "212 KB" },
      { name: "council-memo.docx", combined: false, size: "44 KB" },
    ],
  });
  const update = (patch) => setDraft(d => ({ ...d, ...patch }));

  // completeness calc
  const completeness = React.useMemo(() => {
    let score = 0; const total = 7;
    if (draft.matterType) score++;
    if (draft.title.length > 0 && draft.title.length <= 50) score++;
    if (draft.question.length >= 50) score++;
    if (draft.department) score++;
    if (draft.team) score++;
    if (draft.attachments.length >= 2) score++;
    if (draft.matterType !== "Ordinance" || draft.bieFiled) score++;
    return Math.round((score / total) * 100);
  }, [draft]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", overflow: "hidden", background: "var(--bg)" }}>
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "12px 20px", borderBottom: "1px solid var(--border)",
        background: "var(--bg)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button onClick={() => go("dashboard")} style={{ background: "none", border: "none", display: "flex", alignItems: "center", gap: 5, color: "var(--ink-3)", fontSize: 12, cursor: "pointer" }}><I.ArrowL size={13} />Cancel</button>
          <span style={{ width: 1, height: 16, background: "var(--border)" }} />
          <span className="mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>RLS-26-DRAFT-008</span>
          <Pill tone="default" dot>Draft</Pill>
          <span style={{ fontSize: 11.5, color: "var(--ink-3)" }}>auto-saved 3s ago</span>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <Btn variant="ghost" size="sm" icon={<I.Eye size={13} />}>Preview as PDF</Btn>
          <Btn variant="default" size="sm">Save & exit</Btn>
          <Btn variant="primary" size="sm" iconRight={<I.Arrow size={13} />} disabled={completeness < 80}>Submit</Btn>
        </div>
      </div>

      {/* 3-pane */}
      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "240px minmax(0, 1.2fr) minmax(0, 1fr)", overflow: "hidden" }}>
        {/* LEFT: timeline */}
        <div style={{ borderRight: "1px solid var(--border)", overflowY: "auto", paddingTop: 8, background: "color-mix(in oklab, var(--muted) 35%, white)" }}>
          <ComplianceGraph step={step - 1} completeness={completeness} draft={draft} />
        </div>

        {/* CENTER: form */}
        <div style={{ overflowY: "auto", padding: "20px 24px 32px" }}>
          <WizardCenter step={step} draft={draft} update={update} setStep={setStep} />
        </div>

        {/* RIGHT: live preview */}
        <div style={{ borderLeft: "1px solid var(--border)", background: "color-mix(in oklab, var(--muted) 25%, white)", overflowY: "auto" }}>
          <LivePreview draft={draft} completeness={completeness} />
        </div>
      </div>

      {/* footer step nav */}
      <div style={{
        height: 48, padding: "0 20px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        borderTop: "1px solid var(--border)", background: "var(--canvas)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <Btn variant="default" size="md" icon={<I.ArrowL size={13} />} disabled={step === 1} onClick={() => setStep(s => Math.max(1, s - 1))}>Back</Btn>
          <span className="mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>step {step} of 5</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 11.5, color: "var(--ink-3)", display: "flex", alignItems: "center", gap: 6 }}>
            <I.Sparkles size={12} style={{ color: "var(--primary)" }} />
            AI co-pilot is watching · 3 suggestions
          </span>
          <Btn variant="primary" size="md" iconRight={<I.Arrow size={13} />} onClick={() => setStep(s => Math.min(5, s + 1))}>
            {step === 5 ? "Submit RLS" : "Continue"}
          </Btn>
        </div>
      </div>
    </div>
  );
};

const WizardCenter = ({ step, draft, update, setStep }) => {
  if (step === 1) return <StepMatterType draft={draft} update={update} setStep={setStep} />;
  if (step === 2) return <StepQuestion draft={draft} update={update} />;
  if (step === 3) return <StepRouting draft={draft} update={update} />;
  if (step === 4) return <StepAttachments draft={draft} update={update} />;
  return <StepReview draft={draft} />;
};

const StepHeader = ({ overline, title, sub }) => (
  <div style={{ marginBottom: 18 }}>
    <div style={{ fontSize: 10.5, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.6, color: "var(--primary)" }}>{overline}</div>
    <h2 style={{ fontSize: 22, fontWeight: 600, margin: "4px 0 5px", letterSpacing: -0.3, color: "var(--ink)" }}>{title}</h2>
    {sub && <div style={{ fontSize: 12.5, color: "var(--ink-3)", maxWidth: 540 }}>{sub}</div>}
  </div>
);

const StepMatterType = ({ draft, update, setStep }) => (
  <div>
    <StepHeader overline="Step 1 of 5" title="What kind of matter is this?" sub="The category drives compliance rules, default routing, and which fields appear next. The AI co-pilot has pre-classified your last 3 emails." />
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
      <MatterTypeCard
        title="Litigation"
        desc="Active or threatened lawsuit, appeal, or pre-suit demand against the County."
        icon={<I.Scale size={15} />}
        selected={draft.matterType === "Litigation"}
        onClick={() => update({ matterType: "Litigation" })}
      />
      <MatterTypeCard
        title="Proposed ordinance"
        desc="Draft regulation, code amendment, or resolution requiring legal sufficiency review."
        icon={<I.Doc size={15} />}
        hint="Predicted from your draft text · 92% match"
        badge={<Pill tone="primary" dot>Suggested</Pill>}
        selected={draft.matterType === "Ordinance"}
        onClick={() => update({ matterType: "Ordinance" })}
      />
      <MatterTypeCard
        title="Code enforcement"
        desc="Zoning, building, or land-use violation referred for litigation support."
        icon={<I.Building size={15} />}
        selected={draft.matterType === "Code Enforcement"}
        onClick={() => update({ matterType: "Code Enforcement" })}
      />
      <MatterTypeCard
        title="Contract review"
        desc="New agreement, amendment, or termination requiring sufficiency before signature."
        icon={<I.Doc size={15} />}
        selected={draft.matterType === "Contract"}
        onClick={() => update({ matterType: "Contract" })}
      />
      <MatterTypeCard
        title="Public records"
        desc="Chapter 119 request, exemption review, or production dispute."
        icon={<I.Lock size={15} />}
        selected={draft.matterType === "Public Records"}
        onClick={() => update({ matterType: "Public Records" })}
      />
      <MatterTypeCard
        title="Advisory opinion"
        desc="General legal question without immediate transaction or matter."
        icon={<I.Info size={15} />}
        selected={draft.matterType === "Advisory"}
        onClick={() => update({ matterType: "Advisory" })}
      />
    </div>

    {draft.matterType === "Ordinance" && (
      <AISignal tone="warning" icon={<I.Alert size={12} />} action={{ label: "Add BIE", onClick: () => setStep(3) }}>
        <strong>Heads up:</strong> Proposed ordinances trigger <span className="mono">§125.66(3)(c)</span> Business Impact Estimate. We'll add a BIE worksheet step automatically.
      </AISignal>
    )}
  </div>
);

const StepQuestion = ({ draft, update }) => {
  const titleCount = draft.title.length;
  const titleTone = titleCount > 50 ? "danger" : titleCount > 42 ? "warning" : "info";
  const qLen = draft.question.length;

  return (
    <div>
      <StepHeader overline="Step 2 of 5" title="Frame the legal question" sub="Be specific — the AI co-pilot will tag governing authorities and find precedents in real time." />

      <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
        <Field label="Subject line" hint="Will appear as the matter title in dashboards and email transmittals." badge={
          <span className={`mono`} style={{
            fontSize: 10.5, fontWeight: 600,
            color: titleTone === "danger" ? "var(--destructive)" : titleTone === "warning" ? "var(--warning)" : "var(--ink-3)",
            background: titleTone === "danger" ? "color-mix(in oklab, var(--destructive) 8%, white)" : "var(--muted)",
            padding: "1px 5px", borderRadius: 4,
          }}>{titleCount}/50</span>
        } gutter="var(--success)">
          <TextInput value={draft.title} onChange={(e) => update({ title: e.target.value.slice(0, 60) })} placeholder="One-sentence summary of the matter" />
          <AISignal tone="info">
            <strong>Suggested rewrite:</strong> <span style={{ color: "var(--ink-2)" }}>“STR ord. amendment — private right of action review”</span> <span style={{ color: "var(--ink-3)" }}>(38 chars · clearer scope)</span>
          </AISignal>
        </Field>

        <Field label="Legal question" hint={`${qLen}/2000 characters · be substantive in this field, never in transmittal email body`} gutter="var(--success)">
          <textarea
            value={draft.question}
            onChange={(e) => update({ question: e.target.value })}
            rows={6}
            style={{
              width: "100%", border: "1px solid var(--border-strong)", borderRadius: 6,
              padding: "10px 12px", fontSize: 13, lineHeight: 1.55, resize: "vertical",
              fontFamily: "inherit", background: "var(--canvas)", outline: "none",
            }}
          />
          <AISignal tone="success" icon={<I.Check size={12} stroke={2.5} />}>
            <strong>Authorities detected:</strong> <span className="mono">Fla. Stat. §125.66(3)(c)</span> · <span className="mono">§166.041</span> · <span className="mono">Phantom Touring v. Affiliated Publications</span> — 4 precedents available.
          </AISignal>
        </Field>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <Field label="Department" hint="Auto-detected from requester profile">
            <TextInput value={draft.department} onChange={(e) => update({ department: e.target.value })} suffix={<I.ChevronDown size={12} style={{ color: "var(--ink-3)" }} />} />
          </Field>
          <Field label="Requester">
            <TextInput value={draft.requester} onChange={(e) => update({ requester: e.target.value })} prefix={<I.User size={12} style={{ color: "var(--ink-3)" }} />} />
          </Field>
        </div>

        <Field label="Urgency">
          <div style={{ display: "flex", gap: 6 }}>
            {["Standard", "Urgent", "Critical"].map(u => {
              const map = { Standard: "default", Urgent: "warning", Critical: "danger" };
              const active = draft.urgency === u;
              return (
                <button key={u} onClick={() => update({ urgency: u })} style={{
                  flex: 1, height: 36,
                  background: active ? (u === "Critical" ? "color-mix(in oklab, var(--destructive) 10%, white)" : u === "Urgent" ? "color-mix(in oklab, var(--warning) 10%, white)" : "var(--muted)") : "var(--canvas)",
                  border: `1.5px solid ${active ? (u === "Critical" ? "var(--destructive)" : u === "Urgent" ? "var(--warning)" : "var(--ink-3)") : "var(--border-strong)"}`,
                  borderRadius: 6, fontSize: 12.5, fontWeight: 600,
                  color: active ? (u === "Critical" ? "var(--destructive)" : u === "Urgent" ? "var(--warning)" : "var(--ink)") : "var(--ink-2)",
                  cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
                }}>
                  <span style={{
                    width: 7, height: 7, borderRadius: 999,
                    background: u === "Critical" ? "var(--destructive)" : u === "Urgent" ? "var(--warning)" : "var(--ink-3)",
                  }} />
                  {u}
                </button>
              );
            })}
          </div>
          {draft.urgency === "Critical" && (
            <AISignal tone="warning" icon={<I.Alert size={12} />}>
              Critical urgency requires <strong>director signature</strong> before submission. We'll auto-route to <strong>Marisol Vega</strong> when you continue.
            </AISignal>
          )}
        </Field>
      </div>
    </div>
  );
};

const StepRouting = ({ draft, update }) => (
  <div>
    <StepHeader overline="Step 3 of 5" title="Routing & deadlines" sub="The AI co-pilot suggests a team based on matter type, recent precedents, and current team load." />

    <Card title="Suggested routing" style={{ marginBottom: 18 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <I.Sparkles size={18} style={{ color: "var(--primary)" }} />
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>Land Use & Planning team</div>
          <div style={{ fontSize: 11.5, color: "var(--ink-3)" }}>R. Patel · 11/14 capacity · 96% precedent match on STR ordinances · 8 working days median</div>
        </div>
        <Btn variant="default" size="sm">Override</Btn>
        <Btn variant="primary" size="sm" icon={<I.Check size={12} stroke={2.5} />} onClick={() => update({ team: "Land Use" })}>{draft.team === "Land Use" ? "Accepted" : "Accept"}</Btn>
      </div>
    </Card>

    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
      <Field label="Requested deadline" hint="Working-day calc excludes weekends + County holidays">
        <TextInput value={draft.deadline} onChange={(e) => update({ deadline: e.target.value })} prefix={<I.Calendar size={12} style={{ color: "var(--ink-3)" }} />} />
      </Field>
      <Field label="BIE posting deadline (auto)" hint="14 days before adoption hearing per §125.66(3)(c)">
        <TextInput value="2026-05-31" disabled prefix={<I.Lock size={12} style={{ color: "var(--ink-4)" }} />} suffix={<Pill tone="success" dot>on track</Pill>} />
      </Field>
    </div>
  </div>
);

const StepAttachments = ({ draft, update }) => (
  <div>
    <StepHeader overline="Step 4 of 5" title="Attachments" sub="Upload each document as a separate file. Combined PDFs are blocked by policy — the chain-of-custody log must reference each artifact independently." />

    <div style={{
      border: "1.5px dashed var(--border-strong)", borderRadius: 10,
      padding: 22, background: "color-mix(in oklab, var(--muted) 30%, white)",
      textAlign: "center", marginBottom: 18,
    }}>
      <I.Paperclip size={20} style={{ color: "var(--ink-3)" }} />
      <div style={{ fontSize: 13, fontWeight: 600, marginTop: 6 }}>Drop files here or browse</div>
      <div style={{ fontSize: 11.5, color: "var(--ink-3)", marginTop: 3 }}>.docx for drafts · .pdf for filed copies · max 25 MB each</div>
    </div>

    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {draft.attachments.map((a, i) => (
        <div key={i} style={{
          display: "grid", gridTemplateColumns: "20px 1fr 70px 70px 24px", gap: 10, alignItems: "center",
          padding: "8px 12px", background: "var(--canvas)",
          border: "1px solid var(--border)", borderRadius: 6,
        }}>
          <I.Doc size={14} style={{ color: "var(--ink-3)" }} />
          <span style={{ fontSize: 12.5, fontWeight: 500, fontFamily: "var(--mono)" }}>{a.name}</span>
          <span style={{ fontSize: 11, color: "var(--ink-3)" }}>{a.size}</span>
          <Pill tone={a.combined ? "danger" : "success"} dot>{a.combined ? "combined" : "individual"}</Pill>
          <I.X size={13} style={{ color: "var(--ink-4)", cursor: "pointer" }} />
        </div>
      ))}
    </div>

    <AISignal tone="info" action={{ label: "Generate", onClick: () => {} }}>
      We can auto-generate a <strong>transmittal email + attachment checklist</strong> from these files. The email body will be empty per policy (substantive content stays in the RLS).
    </AISignal>
  </div>
);

const StepReview = ({ draft }) => (
  <div>
    <StepHeader overline="Step 5 of 5" title="Review & submit" sub="A SHA-256 hash of this submission and all attachments is appended to the audit chain at submission time." />

    <Card title="Summary" style={{ marginBottom: 12 }}>
      {[
        ["Matter", draft.matterType],
        ["Subject", draft.title],
        ["Requester / Dept", `${draft.requester} · ${draft.department}`],
        ["Urgency", draft.urgency],
        ["Routed to", draft.team || "—"],
        ["Deadline", draft.deadline],
        ["Attachments", `${draft.attachments.length} files`],
      ].map(([k, v]) => (
        <div key={k} style={{ display: "grid", gridTemplateColumns: "140px 1fr", gap: 12, padding: "5px 0", fontSize: 12.5, borderBottom: "1px dashed var(--border)" }}>
          <span style={{ color: "var(--ink-3)", fontWeight: 500 }}>{k}</span>
          <span style={{ color: "var(--ink)" }}>{v}</span>
        </div>
      ))}
    </Card>

    <AISignal tone="success" icon={<I.Check size={12} stroke={2.5} />}>
      All 8 compliance lanes pass. Ready to submit. Estimated time-to-acknowledgment: <strong>4 hours</strong> based on Land Use team's 30d median.
    </AISignal>
  </div>
);

// === RIGHT pane: live preview as transmittal ===
const LivePreview = ({ draft, completeness }) => (
  <div style={{ padding: 16 }}>
    <div style={{ fontSize: 10.5, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.6, color: "var(--ink-3)", marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
      <I.Eye size={11} /> Live preview · transmittal
    </div>
    <div style={{
      background: "var(--canvas)", border: "1px solid var(--border)", borderRadius: 10,
      padding: 18, fontSize: 12, lineHeight: 1.6, color: "var(--ink-2)",
      boxShadow: "var(--shadow-sm)",
    }}>
      <div style={{ borderBottom: "1px dashed var(--border)", paddingBottom: 8, marginBottom: 10 }}>
        <div className="mono" style={{ fontSize: 10.5, color: "var(--ink-4)" }}>RLS-26-DRAFT-008 · FY26</div>
        <div className="serif" style={{ fontSize: 16, fontWeight: 600, color: "var(--ink)", marginTop: 4, lineHeight: 1.3 }}>
          {draft.title || <span style={{ color: "var(--ink-4)" }}>(subject line will appear here)</span>}
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 8 }}>
          <Pill tone="primary" dot>{draft.matterType}</Pill>
          <UrgencyPill urgency={draft.urgency} />
          {draft.matterType === "Ordinance" && <Pill tone="warning">BIE required</Pill>}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "4px 12px", fontSize: 11.5, marginBottom: 10 }}>
        <span style={{ color: "var(--ink-4)" }}>From</span><span>{draft.requester} · {draft.department}</span>
        <span style={{ color: "var(--ink-4)" }}>To</span><span>{draft.team ? `${draft.team} team` : "—"}</span>
        <span style={{ color: "var(--ink-4)" }}>Deadline</span><span className="mono">{draft.deadline}</span>
      </div>

      <div style={{ fontSize: 12, color: "var(--ink)", whiteSpace: "pre-wrap", lineHeight: 1.65 }} className="serif">
        {draft.question}
      </div>

      <div style={{ marginTop: 14, paddingTop: 10, borderTop: "1px dashed var(--border)" }}>
        <div style={{ fontSize: 10.5, fontWeight: 600, color: "var(--ink-3)", marginBottom: 6, textTransform: "uppercase", letterSpacing: 0.5 }}>Attachments ({draft.attachments.length})</div>
        {draft.attachments.map((a, i) => (
          <div key={i} className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)", display: "flex", justifyContent: "space-between", padding: "2px 0" }}>
            <span>· {a.name}</span><span>{a.size}</span>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 12, paddingTop: 10, borderTop: "1px dashed var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span className="mono" style={{ fontSize: 10, color: "var(--ink-4)" }}>chain-prev: 2c8d…b71e</span>
        <span style={{ fontSize: 10.5, color: "var(--ink-3)" }}>completeness {completeness}%</span>
      </div>
    </div>

    <div style={{ marginTop: 14 }}>
      <div style={{ fontSize: 10.5, fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.6, color: "var(--ink-3)", marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
        <I.Sparkles size={11} style={{ color: "var(--primary)" }} /> AI co-pilot · 3 active suggestions
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {[
          { tone: "info", text: "Tighten subject — currently 53 chars, soft-cap is 50." },
          { tone: "warning", text: "BIE worksheet not yet attached — deadline May 31." },
          { tone: "success", text: "3 precedents matched on STR private right of action — see Library." },
        ].map((s, i) => (
          <AISignal key={i} tone={s.tone}>{s.text}</AISignal>
        ))}
      </div>
    </div>
  </div>
);

window.Wizard = Wizard;
