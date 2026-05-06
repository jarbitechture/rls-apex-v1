// overlay.js — dev-only UI Simplicity Score badge.
// Gated: only mounts when ?ui_simplicity=1 OR localStorage.RLS_UI_SIMPLICITY="1".
// Toggle visibility with Cmd/Ctrl+Shift+S.
// Reads thresholds from /ui-simplicity/thresholds.json (single source).
//
// Depends on metrics.js exposing window.__rlsComputeScore.

(function () {
  const enabled =
    /\bui_simplicity=1\b/.test(location.search) ||
    (typeof localStorage !== "undefined" && localStorage.getItem("RLS_UI_SIMPLICITY") === "1");
  if (!enabled) return;
  if (window.__RLS_UI_SIMPLICITY_OVERLAY__) return;
  window.__RLS_UI_SIMPLICITY_OVERLAY__ = true;

  let thresholds = null;

  // Relative path so this works on both FastAPI (served at /) and GitHub
  // Pages (served at /<repo>/). Resolves against the page's baseURI.
  const _thresholdsURL = new URL("ui-simplicity/thresholds.json", document.baseURI).href;
  fetch(_thresholdsURL, { cache: "no-store" })
    .then((r) => r.json())
    .then((t) => { thresholds = t; mount(); refresh(); })
    .catch((e) => console.warn("[ui-simplicity] thresholds load failed", e));

  function mount() {
    if (document.getElementById("rls-ui-simplicity")) return;
    const el = document.createElement("div");
    el.id = "rls-ui-simplicity";
    el.innerHTML = `
      <div class="rls-uis-head">
        <span class="rls-uis-score">--</span>
        <span class="rls-uis-sev"></span>
        <button class="rls-uis-min" title="Toggle (Cmd+Shift+S)">−</button>
      </div>
      <ol class="rls-uis-issues"></ol>
      <div class="rls-uis-foot">UI Simplicity · v${(thresholds && thresholds.version) || 1}</div>
    `;
    Object.assign(el.style, {
      position: "fixed", left: "16px", bottom: "16px", width: "280px",
      background: "#fff", border: "1px solid #e6e5e1", borderRadius: "10px",
      padding: "10px 12px", boxShadow: "0 8px 22px rgba(0,0,0,0.08)",
      fontFamily: 'ui-monospace, "SF Mono", Consolas, monospace',
      fontSize: "11px", color: "#1A1A1A", zIndex: "9998",
    });
    const css = document.createElement("style");
    css.textContent = `
      #rls-ui-simplicity .rls-uis-head { display:flex; align-items:center; gap:8px; }
      #rls-ui-simplicity .rls-uis-score { font-size: 22px; font-weight: 700; line-height: 1; }
      #rls-ui-simplicity .rls-uis-sev { font-size: 10px; padding: 2px 7px; border-radius: 999px; text-transform: uppercase; letter-spacing: 0.06em; }
      #rls-ui-simplicity .rls-uis-sev.info { background:#e8f4ee; color:#1F8A4C; }
      #rls-ui-simplicity .rls-uis-sev.warn { background:#fdf2dd; color:#B86E0A; }
      #rls-ui-simplicity .rls-uis-sev.fail { background:#fbe9e6; color:#C7361B; }
      #rls-ui-simplicity .rls-uis-min  { margin-left:auto; background:transparent; border:0; color:#80807B; cursor:pointer; font-size: 14px; padding: 0 4px; line-height:1; }
      #rls-ui-simplicity .rls-uis-issues { margin: 8px 0 4px; padding-left: 16px; color:#4A4A47; font-size: 11px; line-height: 1.5; }
      #rls-ui-simplicity .rls-uis-issues li + li { margin-top: 2px; }
      #rls-ui-simplicity .rls-uis-foot { color:#A0A09A; font-size: 9px; }
      #rls-ui-simplicity.minimized .rls-uis-issues,
      #rls-ui-simplicity.minimized .rls-uis-foot { display: none; }
    `;
    document.head.appendChild(css);
    document.body.appendChild(el);

    el.querySelector(".rls-uis-min").addEventListener("click", () => el.classList.toggle("minimized"));
  }

  let pending = null;
  function refresh() {
    if (!thresholds || typeof window.__rlsComputeScore !== "function") return;
    if (pending) cancelAnimationFrame(pending);
    pending = requestAnimationFrame(() => {
      const r = window.__rlsComputeScore(document, { w: innerWidth, h: innerHeight }, thresholds);
      const el = document.getElementById("rls-ui-simplicity");
      if (!el) return;
      el.querySelector(".rls-uis-score").textContent = r.score;
      const sev = el.querySelector(".rls-uis-sev");
      sev.textContent = r.severity; sev.className = "rls-uis-sev " + r.severity;
      const ol = el.querySelector(".rls-uis-issues");
      ol.innerHTML = r.issues.slice(0, 3)
        .map((i) => `<li>${escapeHtml(i.label)} (${escapeHtml(i.detail)})</li>`)
        .join("") || `<li style="color:#A0A09A;font-style:italic">No issues</li>`;
      window.__rls_last_score = r;
    });
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  }

  // Refresh triggers: route changes (DOM mutation), resize, every 1.5s
  // as a safety net so dynamic content (the agent panel, etc.) is captured.
  document.addEventListener("DOMContentLoaded", refresh);
  new MutationObserver(() => refresh()).observe(document.documentElement,
    { attributes: true, subtree: true, childList: true });
  addEventListener("resize", refresh);
  setInterval(refresh, 1500);

  document.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.shiftKey && (e.key === "S" || e.key === "s")) {
      e.preventDefault();
      const el = document.getElementById("rls-ui-simplicity");
      if (el) el.hidden = !el.hidden;
    }
  });
})();
