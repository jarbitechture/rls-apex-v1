import type { CurePathStep, Citation } from "@/lib/rls-api";

export function CurePath({ items, citations }: { items: CurePathStep[]; citations: Citation[] }) {
  if (!items?.length) return null;
  const cmap = new Map(citations.map((c) => [c.id, c]));
  return (
    <section className="mt-5">
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        Cure path · {items.length} step{items.length === 1 ? "" : "s"}
      </div>
      <ol className="space-y-2">
        {items.map((it, i) => (
          <li
            key={i}
            className="grid grid-cols-[28px_1fr] gap-3 rounded-xl border p-4"
            style={{
              background:
                "linear-gradient(135deg, color-mix(in oklab, var(--primary) 5%, var(--background)), var(--background))",
              backdropFilter: "blur(14px) saturate(150%)",
              WebkitBackdropFilter: "blur(14px) saturate(150%)",
              borderColor: "color-mix(in oklab, var(--primary) 18%, transparent)",
              boxShadow: `
                0 1px 0 color-mix(in oklab, white 70%, transparent) inset,
                0 8px 20px -10px color-mix(in oklab, var(--primary) 22%, transparent),
                0 1px 3px -1px rgba(0,0,0,0.05)
              `,
            }}
          >
            <div className="grid h-6 w-6 place-items-center rounded-full bg-primary/15 text-[11px] font-bold text-primary">
              {i + 1}
            </div>
            <div>
              <div className="text-sm font-semibold leading-snug">{it.title}</div>
              <div className="mt-1 text-[13px] leading-relaxed text-muted-foreground">{it.detail}</div>
              {it.citation_id && (
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="font-mono text-[11px] font-semibold text-primary">{it.citation_id}</span>
                  {cmap.get(it.citation_id)?.pinpoint && (
                    <span className="font-mono text-[11px] text-muted-foreground">
                      · {cmap.get(it.citation_id)!.pinpoint}
                    </span>
                  )}
                </div>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
