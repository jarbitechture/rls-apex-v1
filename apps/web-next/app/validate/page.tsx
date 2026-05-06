"use client";

import { useRef, useState } from "react";
import { Bolt, Check, X, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import {
  streamSSE,
  RLS_API,
  type Citation,
  type DonePayload,
} from "@/lib/rls-api";
import { ScoreBlock } from "@/components/validate/score-block";
import { CurePath } from "@/components/validate/cure-path";

const STEP_LABEL: Record<string, string> = {
  classify: "classify",
  "retrieve.hybrid": "retrieve",
  "policy_graph.cited_by": "graph",
  rank: "rank",
  compose: "compose",
};

const SAMPLE_DRAFTS = [
  "Can the County contract a sole-source IT vendor under §125.65 if findings are drafted concurrently?",
  "Is a 60-month evergreen renewal enforceable against the County?",
  "Vested rights claim under prior LDC §6.4.A.5 for a setback variance — is this defensible?",
  "Can we exempt these civil-litigation records under §119.071(2)(d)?",
];

type Step = { name: string; status: "active" | "done"; duration_ms?: number };

export default function ValidatePage() {
  const [draft, setDraft] = useState("");
  const [validating, setValidating] = useState(false);
  const [steps, setSteps] = useState<Step[]>([]);
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<Citation[]>([]);
  const [done, setDone] = useState<DonePayload | null>(null);
  const [decision, setDecision] = useState<"accept" | "reject" | "return" | null>(null);
  const stepStarts = useRef<Record<string, number>>({});

  async function handleValidate() {
    const q = draft.trim();
    if (!q || validating) return;
    setValidating(true);
    setSteps([]);
    setAnswer("");
    setCitations([]);
    setDone(null);
    setDecision(null);
    stepStarts.current = {};

    try {
      await streamSSE("/api/query", { q }, ({ event, data }) => {
        if (event === "step") {
          const d = data as { name: string; status: "start" | "done"; t_ms?: number };
          if (d.name === "_chain") return;
          if (d.status === "start") {
            stepStarts.current[d.name] = d.t_ms ?? 0;
            setSteps((prev) => [
              ...prev.filter((s) => s.name !== d.name),
              { name: d.name, status: "active" },
            ]);
          } else if (d.status === "done") {
            const start = stepStarts.current[d.name] ?? 0;
            const ms = d.t_ms != null ? d.t_ms - start : undefined;
            setSteps((prev) => [
              ...prev.filter((s) => s.name !== d.name),
              { name: d.name, status: "done", duration_ms: ms },
            ]);
          }
        } else if (event === "token") {
          setAnswer((prev) => prev + (data as { text: string }).text);
        } else if (event === "citation") {
          setCitations((prev) => [...prev, data as Citation]);
        } else if (event === "done") {
          setDone(data as DonePayload);
        }
      });
    } catch (e) {
      toast.error("Validate failed", { description: (e as Error).message });
    } finally {
      setValidating(false);
    }
  }

  async function handleDecision(d: "accept" | "reject" | "return") {
    if (!done) return;
    try {
      await RLS_API.feedback.send(d, {
        question: draft,
        intent: done.intent,
        lineage_id: done.lineage_id,
      });
      setDecision(d);
      toast.success(`${d.charAt(0).toUpperCase() + d.slice(1)}ed — logged`);
    } catch (e) {
      toast.error("Feedback failed", { description: (e as Error).message });
    }
  }

  function reset() {
    setDraft("");
    setSteps([]);
    setAnswer("");
    setCitations([]);
    setDone(null);
    setDecision(null);
  }

  const hasResult = answer.length > 0 || citations.length > 0 || done != null;

  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Header */}
      <header className="border-b px-8 py-5">
        <div className="flex items-baseline gap-3">
          <h1 className="font-serif text-2xl font-semibold tracking-tight">Validate</h1>
          <Badge variant="secondary" className="font-mono text-[10px] uppercase tracking-wider">
            FY26 · Q3
          </Badge>
        </div>
        <p className="mt-1 max-w-3xl text-[13px] text-muted-foreground">
          Paste a draft RLS — the gateway grades it against the County Attorney corpus and returns
          a rejection-probability score with cure path. Citations are real; the LLM call is mocked
          until SGLang lands.
        </p>
      </header>

      {/* Body */}
      <div className="flex-1 overflow-auto">
        <div className="mx-auto max-w-3xl px-8 py-8 pb-24">
          {/* Input */}
          <label className="mb-2 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Draft RLS
          </label>
          <Textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Paste the legal question and supporting facts. Plain text is fine."
            disabled={validating}
            className="min-h-[140px] resize-y text-sm leading-relaxed"
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === "Enter") void handleValidate();
            }}
          />

          {!hasResult && !validating && (
            <div className="mt-3 flex flex-wrap gap-2">
              {SAMPLE_DRAFTS.map((s) => (
                <button
                  key={s}
                  onClick={() => setDraft(s)}
                  className="rounded-full border bg-background px-3 py-1 text-[11.5px] text-muted-foreground transition hover:border-primary hover:text-foreground"
                >
                  {s.length > 64 ? s.slice(0, 61) + "…" : s}
                </button>
              ))}
            </div>
          )}

          <div className="mt-4 flex items-center gap-2">
            <Button
              onClick={handleValidate}
              disabled={!draft.trim() || validating}
              className="gap-2"
            >
              <Bolt className="h-3.5 w-3.5" />
              {validating ? "Validating…" : "Validate"}
            </Button>
            {(hasResult || draft) && (
              <Button variant="ghost" onClick={reset}>
                Clear
              </Button>
            )}
            <span className="ml-auto font-mono text-[11px] text-muted-foreground">
              POST /api/query · SSE · ⌘⏎ submits
            </span>
          </div>

          {/* Step trace */}
          {(validating || steps.length > 0) && (
            <div className="mt-5 flex flex-wrap gap-1.5">
              {steps.map((s) => (
                <span
                  key={s.name}
                  className={
                    "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[10.5px] " +
                    (s.status === "done"
                      ? "border-emerald-500/50 text-emerald-700"
                      : "border-primary/60 text-primary")
                  }
                >
                  <span
                    className={
                      "h-1.5 w-1.5 rounded-full " +
                      (s.status === "done" ? "bg-emerald-500" : "animate-pulse bg-primary")
                    }
                  />
                  {STEP_LABEL[s.name] ?? s.name}
                  {s.duration_ms != null && (
                    <span className="text-muted-foreground">· {s.duration_ms}ms</span>
                  )}
                </span>
              ))}
            </div>
          )}

          {/* 1. Score */}
          {done?.score != null && (
            <div className="mt-6">
              <ScoreBlock score={done.score} band={done.band} intent={done.intent} />
            </div>
          )}

          {/* 2. Cure path */}
          {done?.cure_path && (
            <CurePath items={done.cure_path} citations={citations} />
          )}

          {/* 3. Reasoning */}
          {hasResult && answer && (
            <section className="mt-5">
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Reasoning
              </div>
              <div className="whitespace-pre-wrap rounded-xl border bg-card px-5 py-4 text-sm leading-relaxed">
                {answer}
              </div>
            </section>
          )}

          {/* 4. Citations */}
          {citations.length > 0 && (
            <section className="mt-5">
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Citations
              </div>
              <div className="space-y-2">
                {citations.map((c, i) => (
                  <div key={c.id ?? i} className="rounded-lg border bg-card px-4 py-3">
                    <div className="flex items-baseline gap-2">
                      <span className="font-mono text-[12px] font-semibold text-primary">{c.id}</span>
                      <span className="font-mono text-[11px] text-muted-foreground">
                        {c.source_kind} · {c.pinpoint}
                      </span>
                    </div>
                    <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">
                      {c.excerpt}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* 5. Decision row */}
          {done && (
            <div className="mt-6 flex flex-wrap items-center gap-2 border-t pt-5">
              <Button
                variant={decision === "accept" ? "default" : "outline"}
                onClick={() => handleDecision("accept")}
                disabled={!!decision}
                className="gap-1.5"
              >
                <Check className="h-3.5 w-3.5" />
                {decision === "accept" ? "Accepted" : "Accept"}
              </Button>
              <Button
                variant={decision === "reject" ? "destructive" : "outline"}
                onClick={() => handleDecision("reject")}
                disabled={!!decision}
                className="gap-1.5"
              >
                <X className="h-3.5 w-3.5" />
                {decision === "reject" ? "Rejected" : "Reject"}
              </Button>
              <Button
                variant={decision === "return" ? "secondary" : "outline"}
                onClick={() => handleDecision("return")}
                disabled={!!decision}
                className="gap-1.5"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                {decision === "return" ? "Returned" : "Return for revision"}
              </Button>
              <span className="ml-auto font-mono text-[10.5px] text-muted-foreground">
                {done.prompt_tokens} in · {done.output_tokens} out · {done.lineage_id} ·{" "}
                {done.citations_source}
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
