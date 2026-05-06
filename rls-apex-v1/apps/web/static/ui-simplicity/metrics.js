// metrics.js — pure UI-simplicity scorer. Used by both the dev overlay
// (apps/web/static/ui-simplicity/overlay.js) and the CI check
// (eval/ui-simplicity/check.mjs). Single source of truth.
//
// Exposes window.__rlsComputeScore(document, { w, h }, thresholds) when
// loaded as a script. Also exports computeScore for ESM-aware callers.

(function (root) {
  // ─── visibility helpers ─────────────────────────────────────────
  function isVisible(el, vp) {
    if (!el || el.nodeType !== 1) return false;
    const cs = (el.ownerDocument.defaultView || window).getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || parseFloat(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    if (r.bottom <= 0 || r.right <= 0) return false;
    if (r.top >= vp.h || r.left >= vp.w) return false;
    return true;
  }

  function visibleArea(el, vp) {
    const r = el.getBoundingClientRect();
    const w = Math.max(0, Math.min(r.right, vp.w) - Math.max(r.left, 0));
    const h = Math.max(0, Math.min(r.bottom, vp.h) - Math.max(r.top, 0));
    return w * h;
  }

  // ─── interactive above-fold count ───────────────────────────────
  function countInteractive(doc, vp) {
    const sel = "button, a[href], [role='button'], input:not([type=hidden]), select, textarea, [tabindex]:not([tabindex='-1'])";
    let n = 0;
    for (const el of doc.querySelectorAll(sel)) {
      if (isVisible(el, vp)) n++;
    }
    return n;
  }

  // ─── distinct font sizes / colors ───────────────────────────────
  function countTypography(doc, vp) {
    const sizes = new Set();
    const colors = new Set();
    const view = doc.defaultView || window;
    const walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_ELEMENT, {
      acceptNode: (el) => {
        if (!isVisible(el, vp)) return NodeFilter.FILTER_REJECT;
        // Only sample elements that hold visible text.
        let hasText = false;
        for (const c of el.childNodes) {
          if (c.nodeType === 3 && c.textContent.trim().length > 0) { hasText = true; break; }
        }
        return hasText ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_SKIP;
      }
    });
    let cur = walker.nextNode();
    while (cur) {
      const cs = view.getComputedStyle(cur);
      // Round font-size to integer px to avoid noise from sub-pixel scaling
      sizes.add(Math.round(parseFloat(cs.fontSize)));
      colors.add(normalizeColor(cs.color));
      cur = walker.nextNode();
    }
    return { fontSizes: sizes.size, colors: colors.size };
  }

  function normalizeColor(c) {
    // Strip alpha + round each channel to nearest 0x10 so subtle hover-state
    // tints don't inflate the distinct-color count.
    const m = c.match(/rgba?\(([^)]+)\)/i);
    if (!m) return c.replace(/\s+/g, "").toLowerCase();
    const parts = m[1].split(",").slice(0, 3).map((p) => Math.round(parseFloat(p) / 16) * 16);
    return `rgb(${parts.join(",")})`;
  }

  // ─── panels / overlays ──────────────────────────────────────────
  function countPanels(doc, vp) {
    const sel = [
      "[role='dialog']",
      "[role='alertdialog']",
      ".modal",
      ".drawer",
      ".popover",
      ".tweaks-panel",
      "[data-panel]",
      "#rls-agent-panel:not([hidden])",
    ].join(", ");
    let n = 0;
    for (const el of doc.querySelectorAll(sel)) {
      if (isVisible(el, vp)) n++;
    }
    return n;
  }

  // ─── KPI cards (heuristic) ──────────────────────────────────────
  // The prototype's dashboard tiles don't share a single class. We use a
  // heuristic: visible elements whose classnames hint at metrics/cards/tiles
  // AND whose text contains a number-like token (e.g. "47", "94%").
  function countKpiCards(doc, vp) {
    const sel = "[class*='kpi'], [class*='metric'], [class*='tile'], [class*='stat'], [class*='card']";
    const numLike = /(?:^|\s)(\d{1,4}(?:\.\d+)?%?|\d+\.\d+d|\d+:\d+)(?:$|\s)/m;
    let n = 0;
    for (const el of doc.querySelectorAll(sel)) {
      if (!isVisible(el, vp)) continue;
      const txt = (el.textContent || "").trim();
      if (txt.length > 0 && numLike.test(txt)) n++;
    }
    return n;
  }

  // ─── AI widgets ─────────────────────────────────────────────────
  function countAiWidgets(doc, vp) {
    const sel = [
      "#rls-agent-panel:not([hidden])",
      "[class*='copilot']",
      "[class*='co-pilot']",
      "[class*='ai-widget']",
      "[class*='ai-suggestion']",
      "[data-ai='true']",
    ].join(", ");
    let n = 0;
    const seen = new WeakSet();
    for (const el of doc.querySelectorAll(sel)) {
      if (!isVisible(el, vp) || seen.has(el)) continue;
      seen.add(el); n++;
    }
    return n;
  }

  // ─── density ────────────────────────────────────────────────────
  function densityScore(interactive, vp) {
    const area = (vp.w * vp.h) / 1000; // 1000 px² units
    return area > 0 ? interactive / area : 0;
  }

  // ─── score ──────────────────────────────────────────────────────
  function computeScore(doc, vp, thresholds) {
    const interactiveAboveFold = countInteractive(doc, vp);
    const typo = countTypography(doc, vp);
    const counts = {
      interactiveAboveFold,
      fontSizes: typo.fontSizes,
      colors: typo.colors,
      panels: countPanels(doc, vp),
      kpiCards: countKpiCards(doc, vp),
      aiWidgets: countAiWidgets(doc, vp),
      density: Math.round(densityScore(interactiveAboveFold, vp) * 1000) / 1000,
    };

    let total = 0;
    const issues = [];
    for (const m of thresholds.metrics) {
      const observed = counts[m.key];
      if (observed == null) continue;
      if (observed > m.soft) {
        const excess = observed - m.soft;
        const penalty = m.perUnit
          ? (excess / m.perUnit) * m.penalty
          : excess * m.penalty;
        total += penalty;
        issues.push({
          key: m.key,
          label: m.label,
          count: observed,
          cap: m.soft,
          penalty: Math.round(penalty * 10) / 10,
          detail: m.perUnit
            ? `${observed.toFixed(3)} vs cap ${m.soft.toFixed(3)}`
            : `${observed} vs cap of ${m.soft}`,
        });
      }
    }
    issues.sort((a, b) => b.penalty - a.penalty);

    const score = Math.max(0, Math.round(100 - total));
    const severity = score >= 80 ? "info" : score >= 60 ? "warn" : "fail";
    return { score, severity, issues, counts };
  }

  // expose
  root.__rlsComputeScore = computeScore;
  if (typeof module !== "undefined" && module.exports) module.exports = { computeScore };
})(typeof window !== "undefined" ? window : globalThis);
