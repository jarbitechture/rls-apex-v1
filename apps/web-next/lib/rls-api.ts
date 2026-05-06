/**
 * RLS API client — same contract as the legacy rls-api.js global, but
 * properly typed and tree-shakeable.
 *
 * The gateway sets up DEV_AUTH_BYPASS=1 + RLS_ALLOWLIST=BCC\ejarbeadm
 * by default in `bin/dev`. Endpoints live at /api/* on the gateway
 * (default localhost:8080 for the legacy build, 8090 in this session).
 *
 * On GitHub Pages there is no gateway — `fetch` will fail and callers
 * should fall back to graceful empty/offline states.
 */

// Resolve the gateway base URL. In dev, use NEXT_PUBLIC_RLS_BASE if set,
// else default to a relative path (gateway serves the static bundle, so
// same-origin works). On Pages there is no gateway; calls fail and the
// app degrades to offline mode.
export const RLS_BASE = (process.env.NEXT_PUBLIC_RLS_BASE ?? "").replace(/\/+$/, "");

export type Citation = {
  id: string;
  source: string;
  source_kind: string;
  pinpoint: string;
  excerpt: string;
  score?: number;
};

export type CurePathStep = {
  title: string;
  detail: string;
  citation_id?: string;
};

export type DonePayload = {
  prompt_tokens?: number;
  output_tokens?: number;
  lineage_id: string;
  intent: string;
  score?: number;
  band?: "low" | "medium" | "high" | "likely_rejected";
  cure_path?: CurePathStep[];
  citations_source?: "corpus" | "canned" | "none";
  llm_provider?: string;
};

export type CorpusDoc = {
  id: string;
  source: string;
  source_kind: string;
  classification: "public_record" | "internal" | "privileged";
  pages: number;
  chunks: number;
  bytes: number;
  hash: string;
};

export type Me = {
  upn: string;
  display_name: string;
  initials: string;
  role: string;
};

export type SSEEvent =
  | { event: "step"; data: { name: string; status: "start" | "done"; t_ms?: number; output?: unknown } }
  | { event: "token"; data: { text: string } }
  | { event: "citation"; data: Citation }
  | { event: "done"; data: DonePayload }
  | { event: string; data: unknown };

class APIError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(RLS_BASE + path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    credentials: "same-origin",
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new APIError(`${res.status} ${res.statusText}: ${body}`, res.status);
  }
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/json")) return res.json();
  return res.text() as unknown as T;
}

export const RLS_API = {
  me:    ()       => request<Me>("/api/me"),
  corpus: ()      => request<{ loaded: boolean; documents: CorpusDoc[]; total_chunks: number }>("/api/corpus"),
  feedback: {
    send:  (decision: "accept" | "reject" | "return", ctx: Record<string, unknown>) =>
      request<{ ok: boolean; decision: string }>("/api/feedback",
        { method: "POST", body: JSON.stringify({ decision, ...ctx }) }),
    recent: () => request<{ items: unknown[] }>("/api/feedback/recent"),
  },
};

export { APIError };

/**
 * Stream Server-Sent Events from /api/query (or any SSE endpoint).
 * Calls onEvent for each parsed frame. Throws APIError on non-2xx.
 */
export async function streamSSE(
  path: string,
  body: unknown,
  onEvent: (e: SSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(RLS_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok) throw new APIError(`${res.status} ${res.statusText}`, res.status);
  if (!res.body) throw new APIError("response has no body", 0);

  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let nl: number;
    while ((nl = buf.indexOf("\n\n")) !== -1) {
      const chunk = buf.slice(0, nl);
      buf = buf.slice(nl + 2);
      const lines = chunk.split("\n");
      let evt = "message";
      let data = "";
      for (const l of lines) {
        if (l.startsWith("event:")) evt = l.slice(6).trim();
        else if (l.startsWith("data:")) data = l.slice(5).trim();
      }
      if (!data) continue;
      try { onEvent({ event: evt, data: JSON.parse(data) } as SSEEvent); }
      catch { onEvent({ event: evt, data } as unknown as SSEEvent); }
    }
  }
}
