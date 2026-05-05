// shared primitives — pills, sparklines, chips, buttons, progress bars

const Pill = ({ tone = "default", children, dot, style }) => {
  const tones = {
    default: { bg: "var(--muted)", fg: "var(--ink-2)", dot: "var(--ink-3)" },
    primary: { bg: "color-mix(in oklab, var(--primary) 12%, white)", fg: "var(--primary-ink)", dot: "var(--primary)" },
    success: { bg: "color-mix(in oklab, var(--success) 14%, white)", fg: "var(--success)", dot: "var(--success)" },
    warning: { bg: "color-mix(in oklab, var(--warning) 14%, white)", fg: "var(--warning)", dot: "var(--warning)" },
    info:    { bg: "color-mix(in oklab, var(--info) 12%, white)", fg: "var(--info)", dot: "var(--info)" },
    danger:  { bg: "color-mix(in oklab, var(--destructive) 12%, white)", fg: "var(--destructive)", dot: "var(--destructive)" },
    ghost:   { bg: "transparent", fg: "var(--ink-2)", dot: "var(--ink-3)" },
  };
  const t = tones[tone] || tones.default;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      padding: "2px 7px", borderRadius: 999,
      background: t.bg, color: t.fg,
      fontSize: 11, fontWeight: 500, letterSpacing: 0.1,
      lineHeight: 1.4, whiteSpace: "nowrap",
      ...style,
    }}>
      {dot && <span style={{ width: 5, height: 5, borderRadius: 999, background: t.dot, flex: "none" }} />}
      {children}
    </span>
  );
};

const StatusPill = ({ status }) => {
  const map = {
    Draft: "default",
    Submitted: "info",
    Acknowledged: "warning",
    Assigned: "primary",
    Complete: "success",
    Rejected: "danger",
  };
  return <Pill tone={map[status] || "default"} dot>{status}</Pill>;
};

const UrgencyPill = ({ urgency }) => {
  const map = { Standard: "default", Urgent: "warning", Critical: "danger" };
  return <Pill tone={map[urgency] || "default"}>{urgency}</Pill>;
};

const Sparkline = ({ data, w = 80, h = 22, stroke = "currentColor", fill = "none", strokeWidth = 1.25 }) => {
  if (!data || data.length === 0) return null;
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = max - min || 1;
  const stepX = w / (data.length - 1 || 1);
  const pts = data.map((v, i) => `${(i * stepX).toFixed(2)},${(h - ((v - min) / range) * (h - 2) - 1).toFixed(2)}`).join(" ");
  const area = `0,${h} ${pts} ${w},${h}`;
  return (
    <svg width={w} height={h} style={{ display: "block", overflow: "visible" }}>
      {fill !== "none" && <polygon points={area} fill={fill} />}
      <polyline points={pts} fill="none" stroke={stroke} strokeWidth={strokeWidth} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
};

const Bar = ({ pct, h = 4, color = "var(--primary)", track = "var(--muted-2)", style }) => (
  <div style={{ width: "100%", height: h, background: track, borderRadius: 999, overflow: "hidden", ...style }}>
    <div style={{ width: `${Math.max(0, Math.min(100, pct))}%`, height: "100%", background: color, transition: "width 240ms ease" }} />
  </div>
);

const Btn = ({ variant = "default", size = "md", icon, iconRight, children, onClick, style, disabled, title }) => {
  const variants = {
    primary: { bg: "var(--primary)", fg: "#fff", border: "transparent", hoverBg: "var(--primary-ink)" },
    default: { bg: "var(--canvas)", fg: "var(--ink)", border: "var(--border-strong)", hoverBg: "var(--muted)" },
    ghost:   { bg: "transparent", fg: "var(--ink-2)", border: "transparent", hoverBg: "var(--muted)" },
    soft:    { bg: "var(--muted)", fg: "var(--ink)", border: "transparent", hoverBg: "var(--muted-2)" },
    danger:  { bg: "var(--canvas)", fg: "var(--destructive)", border: "color-mix(in oklab, var(--destructive) 30%, white)", hoverBg: "color-mix(in oklab, var(--destructive) 8%, white)" },
  };
  const sizes = {
    sm: { pad: "4px 8px", h: 24, fs: 12, gap: 5 },
    md: { pad: "6px 12px", h: 30, fs: 13, gap: 6 },
    lg: { pad: "8px 16px", h: 36, fs: 13.5, gap: 8 },
  };
  const v = variants[variant] || variants.default;
  const s = sizes[size];
  const [hover, setHover] = React.useState(false);
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={title}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center", gap: s.gap,
        padding: s.pad, height: s.h, fontSize: s.fs, fontWeight: 500,
        background: hover && !disabled ? v.hoverBg : v.bg,
        color: v.fg,
        border: `1px solid ${v.border}`,
        borderRadius: 6,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        transition: "background 120ms ease",
        whiteSpace: "nowrap",
        ...style,
      }}
    >
      {icon}
      {children && <span>{children}</span>}
      {iconRight}
    </button>
  );
};

const Card = ({ title, action, padding = 16, children, style }) => (
  <div style={{
    background: "var(--canvas)",
    border: "1px solid var(--card-border-color, var(--border))",
    borderRadius: 10,
    boxShadow: "var(--card-shadow, var(--shadow-sm))",
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
    ...style,
  }}>
    {title && (
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "10px 14px",
        borderBottom: "1px solid var(--border)",
        background: "color-mix(in oklab, var(--muted) 50%, white)",
      }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-2)", textTransform: "uppercase", letterSpacing: 0.6 }}>{title}</div>
        {action}
      </div>
    )}
    <div style={{ padding, flex: 1, minHeight: 0 }}>{children}</div>
  </div>
);

// vertical stem chart for short series
const StemChart = ({ data, w = 220, h = 38, color = "var(--primary)", color2 }) => {
  const max = Math.max(...data.flat ? data.flat() : data, 1);
  const isPair = Array.isArray(data[0]);
  const series = isPair ? data : [data];
  const n = series[0].length;
  const slot = w / n;
  return (
    <svg width={w} height={h} style={{ display: "block" }}>
      {series.map((row, sIdx) => row.map((v, i) => {
        const barH = (v / max) * (h - 4);
        const x = i * slot + slot / 2 - (isPair ? 3 : 1) + (isPair ? sIdx * 3 : 0);
        return <rect key={`${sIdx}-${i}`} x={x} y={h - barH - 1} width={2} height={barH} fill={sIdx === 0 ? color : (color2 || color)} rx={1} />;
      }))}
    </svg>
  );
};

// donut for pct
const Donut = ({ pct, size = 56, stroke = 6, color = "var(--primary)", label }) => {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg width={size} height={size}>
        <circle cx={size/2} cy={size/2} r={r} stroke="var(--muted-2)" strokeWidth={stroke} fill="none" />
        <circle cx={size/2} cy={size/2} r={r} stroke={color} strokeWidth={stroke} fill="none"
          strokeDasharray={`${(pct/100)*c} ${c}`} strokeLinecap="round"
          transform={`rotate(-90 ${size/2} ${size/2})`} style={{ transition: "stroke-dasharray 280ms ease" }} />
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", fontSize: 11, fontWeight: 600 }}>
        {label ?? `${pct}%`}
      </div>
    </div>
  );
};

const Field = ({ label, hint, error, children, badge, signal, gutter }) => (
  <div style={{ display: "flex", gap: 12, alignItems: "stretch" }}>
    {gutter && (
      <div style={{ width: 4, borderRadius: 4, background: gutter, flex: "none", marginTop: 22 }} />
    )}
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <label style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-2)", letterSpacing: 0.2 }}>{label}</label>
        {badge}
      </div>
      {children}
      {hint && !error && <div style={{ fontSize: 11.5, color: "var(--ink-3)", marginTop: 5 }}>{hint}</div>}
      {error && <div style={{ fontSize: 11.5, color: "var(--destructive)", marginTop: 5 }}>{error}</div>}
      {signal}
    </div>
  </div>
);

const TextInput = React.forwardRef(({ value, onChange, placeholder, suffix, prefix, style, ...rest }, ref) => (
  <div style={{
    display: "flex", alignItems: "center", gap: 6,
    background: "var(--canvas)",
    border: "1px solid var(--border-strong)",
    borderRadius: 6,
    padding: "0 10px",
    height: 34,
    transition: "border-color 120ms ease, box-shadow 120ms ease",
    ...style,
  }} className="text-input">
    {prefix}
    <input
      ref={ref}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      style={{
        flex: 1, border: "none", outline: "none", background: "transparent",
        fontSize: 13, height: "100%", color: "var(--ink)",
      }}
      {...rest}
    />
    {suffix}
  </div>
));

window.UI = { Pill, StatusPill, UrgencyPill, Sparkline, Bar, Btn, Card, StemChart, Donut, Field, TextInput };
