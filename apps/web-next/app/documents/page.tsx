"use client";

import { useEffect, useMemo, useState } from "react";
import { Eye, FileWarning } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { RLS_API, type CorpusDoc, APIError, RLS_BASE } from "@/lib/rls-api";

type Filt = "all" | string;

export default function DocumentsPage() {
  const [docs, setDocs] = useState<CorpusDoc[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [classFilt, setClassFilt] = useState<Filt>("all");
  const [kindFilt, setKindFilt] = useState<Filt>("all");
  const [reloading, setReloading] = useState(false);

  async function load() {
    try {
      const r = await RLS_API.corpus();
      setDocs(r.documents ?? []);
      setErr(null);
    } catch (e) {
      const isOffline = !(e instanceof APIError);
      setErr(isOffline ? "Gateway not reachable (Pages serves a static demo)" : (e as Error).message);
      setDocs([]);
    }
  }
  useEffect(() => { void load(); }, []);

  async function reload() {
    setReloading(true);
    try {
      await fetch(RLS_BASE + "/api/corpus/reload", { method: "POST" });
      await load();
      toast.success("Index reloaded");
    } catch (e) {
      toast.error("Reload failed", { description: (e as Error).message });
    } finally {
      setReloading(false);
    }
  }

  const all = docs ?? [];
  const allKinds = useMemo(
    () => Array.from(new Set(all.map((d) => d.source_kind))).sort(),
    [all],
  );
  const allClasses = useMemo(
    () => Array.from(new Set(all.map((d) => d.classification))).sort(),
    [all],
  );

  const filtered = all.filter((d) => {
    if (classFilt !== "all" && d.classification !== classFilt) return false;
    if (kindFilt !== "all" && d.source_kind !== kindFilt) return false;
    if (q && !(`${d.source} ${d.id}`.toLowerCase().includes(q.toLowerCase()))) return false;
    return true;
  });
  const totalChunks = filtered.reduce((n, d) => n + (d.chunks ?? 0), 0);

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      <header className="border-b px-8 py-5">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="font-serif text-2xl font-semibold tracking-tight">Documents</h1>
            <p className="mt-1 text-[13px] text-muted-foreground">
              {docs == null
                ? "Loading corpus…"
                : `${filtered.length} of ${all.length} ingested · ${totalChunks} chunks indexed · BM25 retrieval is live`}
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={reload} disabled={reloading || docs == null}>
            <Eye className="mr-1.5 h-3.5 w-3.5" />
            {reloading ? "Reloading…" : "Reload index"}
          </Button>
        </div>

        {/* Filter row */}
        {docs != null && all.length > 0 && (
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search filenames…"
              className="h-8 w-56 text-[13px]"
            />
            <FilterGroup
              label="Class"
              active={classFilt}
              onChange={setClassFilt}
              options={allClasses}
              counts={Object.fromEntries(allClasses.map((c) => [c, all.filter((d) => d.classification === c).length]))}
            />
            <FilterGroup
              label="Kind"
              active={kindFilt}
              onChange={setKindFilt}
              options={allKinds}
              counts={Object.fromEntries(allKinds.map((k) => [k, all.filter((d) => d.source_kind === k).length]))}
            />
          </div>
        )}
      </header>

      <div className="flex-1 overflow-auto p-6">
        {err && (
          <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-4 py-2 text-[13px] text-destructive">
            {err}
          </div>
        )}

        {docs == null ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-28 w-full rounded-xl" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="py-10 text-center text-sm italic text-muted-foreground">
            {all.length === 0
              ? "No documents ingested yet. Drop files into corpus/raw/ and run bin/ingest."
              : "No documents match the current filters."}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((d) => (
              <DocCard key={d.id} d={d} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function FilterGroup({
  label, active, onChange, options, counts,
}: {
  label: string;
  active: Filt;
  onChange: (v: Filt) => void;
  options: string[];
  counts: Record<string, number>;
}) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="mr-1 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <Chip active={active === "all"} onClick={() => onChange("all")}>all</Chip>
      {options.map((o) => (
        <Chip key={o} active={active === o} onClick={() => onChange(o)} count={counts[o]}>
          {o}
        </Chip>
      ))}
    </div>
  );
}

function Chip({
  active, onClick, count, children,
}: {
  active: boolean; onClick: () => void; count?: number; children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={
        "inline-flex h-6 items-center gap-1.5 rounded-full border px-2.5 font-mono text-[11px] transition " +
        (active
          ? "border-primary bg-primary/10 font-semibold text-primary"
          : "border-border bg-card text-muted-foreground hover:border-primary/40 hover:text-foreground")
      }
    >
      {children}
      {count != null && <span className="opacity-70">· {count}</span>}
    </button>
  );
}

function DocCard({ d }: { d: CorpusDoc }) {
  const isPublic = d.classification === "public_record";
  return (
    <Card className="transition hover:shadow-md">
      <CardContent className="p-4">
        <div className="font-mono text-[11px] text-muted-foreground">
          {d.id} · {d.source_kind}
        </div>
        <div className="mt-1.5 line-clamp-2 font-serif text-sm font-semibold leading-snug">
          {d.source}
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Badge variant={isPublic ? "default" : "secondary"} className="text-[10px]">
            {d.classification}
          </Badge>
          <span className="font-mono text-[11px] text-muted-foreground">
            {d.pages}p · {d.chunks}c · {Math.round(d.bytes / 1024)}KB
          </span>
        </div>
        {d.chunks === 0 && (
          <div className="mt-2 flex items-center gap-1.5 text-[11px] text-amber-600">
            <FileWarning className="h-3 w-3" />
            no extractable text — image-only
          </div>
        )}
      </CardContent>
    </Card>
  );
}
