// Rejection-probability score plate. Selective glass aesthetic.

const BAND_STYLE: Record<string, { tint: string; surface: string; chipBg: string; chipFg: string; ink: string; ink2: string; label: string; inv: boolean }> = {
  low: {
    tint: "var(--color-emerald-600, #16a34a)",
    surface: "linear-gradient(135deg, color-mix(in oklab, var(--color-emerald-500, #22c55e) 8%, var(--background)), var(--background))",
    chipBg: "var(--color-emerald-600, #16a34a)", chipFg: "white",
    ink: "var(--color-emerald-700, #15803d)", ink2: "var(--muted-foreground)",
    label: "LOW", inv: false,
  },
  medium: {
    tint: "var(--color-amber-500, #f59e0b)",
    surface: "linear-gradient(135deg, color-mix(in oklab, var(--color-amber-500, #f59e0b) 10%, var(--background)), var(--background))",
    chipBg: "var(--color-amber-500, #f59e0b)", chipFg: "white",
    ink: "var(--color-amber-700, #b45309)", ink2: "var(--muted-foreground)",
    label: "MEDIUM", inv: false,
  },
  high: {
    tint: "var(--color-rose-500, #f43f5e)",
    surface: "linear-gradient(135deg, color-mix(in oklab, var(--color-rose-500, #f43f5e) 12%, var(--background)), var(--background))",
    chipBg: "var(--color-rose-600, #e11d48)", chipFg: "white",
    ink: "var(--color-rose-700, #be123c)", ink2: "var(--muted-foreground)",
    label: "HIGH", inv: false,
  },
  likely_rejected: {
    tint: "var(--color-rose-600, #e11d48)",
    surface: "var(--color-rose-600, #e11d48)",
    chipBg: "color-mix(in oklab, white 18%, transparent)", chipFg: "white",
    ink: "white", ink2: "color-mix(in oklab, white 78%, transparent)",
    label: "LIKELY REJECTED", inv: true,
  },
};

export function ScoreBlock({ score, band, intent }: { score: number; band?: string; intent?: string }) {
  const s = BAND_STYLE[band ?? ""] ?? BAND_STYLE.medium;
  return (
    <div
      className="grid grid-cols-[auto_1fr] items-center gap-4 rounded-xl border p-5"
      style={{
        background: s.surface,
        borderColor: `color-mix(in oklab, ${s.tint} ${s.inv ? 60 : 28}%, transparent)`,
        backdropFilter: "blur(18px) saturate(160%)",
        WebkitBackdropFilter: "blur(18px) saturate(160%)",
        boxShadow: `
          0 1px 0 color-mix(in oklab, white ${s.inv ? 30 : 70}%, transparent) inset,
          0 -1px 0 color-mix(in oklab, ${s.tint} 14%, transparent) inset,
          0 14px 32px -14px color-mix(in oklab, ${s.tint} 38%, transparent),
          0 2px 8px -2px rgba(0, 0, 0, 0.06)
        `,
      }}
    >
      <div>
        <div className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: s.ink, opacity: s.inv ? 0.85 : 1 }}>
          Rejection probability
        </div>
        <div className="mt-1 leading-none" style={{ color: s.ink }}>
          <span className="font-mono text-[34px] font-bold tabular-nums">{score}</span>
          <span className="ml-1 text-sm font-medium opacity-70">/100</span>
        </div>
      </div>
      <div
        className="border-l pl-4"
        style={{ borderColor: `color-mix(in oklab, ${s.tint} ${s.inv ? 30 : 22}%, transparent)` }}
      >
        <span
          className="inline-block rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wider"
          style={{ background: s.chipBg, color: s.chipFg }}
        >
          {s.label}
        </span>
        <div className="mt-1.5 text-[12.5px]" style={{ color: s.ink2 }}>
          Classified as{" "}
          <span className="font-mono font-semibold" style={{ color: s.ink }}>
            {intent || "—"}
          </span>
        </div>
      </div>
    </div>
  );
}
