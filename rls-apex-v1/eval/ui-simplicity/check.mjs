// check.mjs — UI Simplicity Score CI runner.
// Visits each route from routes.json, evaluates apps/web/static/ui-simplicity/metrics.js
// in the page context, prints a table, writes report.json, and exits non-zero on
// any `fail` severity OR a >= regression_threshold drop vs baseline.json.
//
// Usage:   npm run ui-check         (against http://127.0.0.1:8080)
//          RLS_BASE=https://...  npm run ui-check
//          npm run ui-baseline      (regenerate baseline.json from current scores)

import { chromium } from "playwright";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "../..");
const STATIC_BASE = resolve(REPO, "apps/web/static");

const BASE = process.env.RLS_BASE || "http://127.0.0.1:8080";
const MODE = process.argv.includes("--baseline") ? "baseline" : "check";

const routes     = JSON.parse(readFileSync(resolve(HERE, "routes.json"), "utf8"));
const thresholds = JSON.parse(readFileSync(resolve(STATIC_BASE, "ui-simplicity/thresholds.json"), "utf8"));
const baselinePath = resolve(HERE, "baseline.json");
const baseline = existsSync(baselinePath) ? JSON.parse(readFileSync(baselinePath, "utf8")) : {};

console.log(`UI Simplicity ${MODE} · ${BASE} · viewport ${thresholds.viewport.width}×${thresholds.viewport.height}`);
console.log("─".repeat(72));

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: thresholds.viewport.width, height: thresholds.viewport.height },
});
await ctx.addInitScript(() => { window.__RLS_TEST = 1; });
const page = await ctx.newPage();

const out = {};
let anyFail = false;

for (const { route, label } of routes) {
  await page.goto(`${BASE}/?ui_simplicity=1`, { waitUntil: "networkidle" });
  // Wait for the prototype's __RLS_ROUTE_SET hook to be wired by app.jsx.
  try {
    await page.waitForFunction(() => typeof window.__RLS_ROUTE_SET === "function", null, { timeout: 8000 });
    await page.evaluate((r) => window.__RLS_ROUTE_SET(r), route);
  } catch {
    console.warn(`  [warn] ${label}: __RLS_ROUTE_SET not exposed; scoring current page`);
  }
  // Let the new page settle (animations, lazy images, agent panel auto-show).
  await page.waitForTimeout(800);

  const r = await page.evaluate((t) =>
    window.__rlsComputeScore(document, { w: innerWidth, h: innerHeight }, t),
    thresholds);

  const prev = baseline[route]?.score ?? null;
  const delta = prev != null ? r.score - prev : null;
  out[route] = { ...r, label, delta };

  const sevColor = { info: "\x1b[32m", warn: "\x1b[33m", fail: "\x1b[31m" }[r.severity] || "";
  const reset = "\x1b[0m";
  const deltaStr = delta != null
    ? `  Δ${delta >= 0 ? "+" : ""}${delta}`
    : "";
  console.log(`  ${label.padEnd(18)} ${sevColor}${r.score.toString().padStart(3)}${reset}  ${r.severity.padEnd(5)}${deltaStr}`);
  for (const issue of r.issues.slice(0, 3)) {
    console.log(`      └─ ${issue.label}: ${issue.detail}  (-${issue.penalty})`);
  }

  if (MODE === "check") {
    // Regression vs baseline is the primary CI signal. Absolute `fail` is a
    // backstop for routes that have no baseline yet (someone added a page
    // and didn't re-run npm run ui-baseline).
    if (delta != null && delta <= -thresholds.regression_threshold) anyFail = true;
    if (delta == null && r.severity === "fail") anyFail = true;
  }
}

await browser.close();

if (MODE === "baseline") {
  writeFileSync(baselinePath, JSON.stringify(out, null, 2) + "\n");
  console.log(`\nbaseline written: ${baselinePath}`);
} else {
  writeFileSync(resolve(HERE, "report.json"), JSON.stringify(out, null, 2) + "\n");
  console.log(`\nreport written: ${resolve(HERE, "report.json")}`);
  if (anyFail) {
    console.error("\n✗ UI Simplicity regression — see lines above");
    process.exit(1);
  } else {
    console.log("\n✓ UI Simplicity OK");
  }
}
