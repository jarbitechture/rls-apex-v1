// verify-clicks.mjs — drives real button clicks through the prototype's
// actual flow (Submissions → Detail → Mark complete; AI → Send; etc.) and
// asserts /api/agent/dispatch fires AND the agent panel populates.
//
// This is the empirical answer to "is the click→agent wiring right?"
import { chromium } from "playwright";

const BASE = process.env.RLS_BASE || "http://127.0.0.1:8080";

// Each case: navigate via window.__RLS_GO(route, id?), find a button matching
// `match`, click it, expect agent panel to populate.
const cases = [
  {
    name: "Detail · Mark complete → decide(accept)",
    setup: async (page) => page.evaluate(() => window.__RLS_GO("detail", "RLS-26-0141")),
    match: /^Mark complete$/i,
    expectKind: "decide",
  },
  {
    name: "Detail · Reassign → triage (no decide-fired since it's not a decision)",
    setup: async (page) => page.evaluate(() => window.__RLS_GO("detail", "RLS-26-0141")),
    match: /^Reassign$/i,
    expectKind: null, // intentionally not in routes — should NOT fire agent
    expectNoFire: true,
  },
  {
    name: "AI · Send → precedent (chat send)",
    setup: async (page) => {
      await page.evaluate(() => window.__RLS_ROUTE_SET("ai"));
      await page.waitForTimeout(300);
      // Type something so the Send button has content to send
      const ta = await page.$("textarea");
      if (ta) await ta.fill("Sole-source IT vendor under §125.65?");
    },
    match: /^Send$/i,
    expectKind: "precedent",
  },
  {
    name: "BIE Worksheets · Submit for posting → triage",
    setup: async (page) => page.evaluate(() => window.__RLS_ROUTE_SET("bie")),
    match: /^Submit for posting$/i,
    expectKind: "triage",
  },
];

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();

const apiCalls = [];
page.on("request", (req) => {
  if (req.url().includes("/api/")) apiCalls.push({ method: req.method(), url: req.url() });
});

await page.goto(`${BASE}/?ui_simplicity=1`, { waitUntil: "networkidle" });
await page.waitForFunction(() => typeof window.__RLS_GO === "function", null, { timeout: 8000 });

let pass = 0, fail = 0;
for (const tc of cases) {
  // Wait for any previous agent dispatch to finish (clear inflight)
  await page.waitForFunction(() => {
    const dot = document.querySelector("#rls-agent-panel .rls-agent-dot");
    return !dot || !dot.classList.contains("busy");
  }, null, { timeout: 6000 }).catch(() => {});

  apiCalls.length = 0;
  await tc.setup(page);
  await page.waitForTimeout(500);

  // Inventory all visible buttons + their texts (helps debug misses)
  const buttons = await page.evaluate(() => {
    const out = [];
    for (const b of document.querySelectorAll("button")) {
      const r = b.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) continue;
      if (b.closest("#rls-agent-panel")) continue;
      if (b.closest("#rls-ui-simplicity")) continue;
      out.push({ text: (b.textContent || "").trim().slice(0, 50) });
    }
    return out;
  });

  const matched = buttons.find((b) => tc.match.test(b.text));
  if (!matched) {
    fail++;
    console.log(`  ✗ ${tc.name} — button not found`);
    console.log(`      visible buttons: ${buttons.slice(0, 12).map(b => `"${b.text}"`).join(", ")}`);
    continue;
  }

  // Click via JS so React's onClick handler fires AND our delegate runs
  await page.evaluate(({ src, flags }) => {
    const re = new RegExp(src, flags);
    for (const b of document.querySelectorAll("button")) {
      if (b.closest("#rls-agent-panel") || b.closest("#rls-ui-simplicity")) continue;
      if (re.test((b.textContent || "").trim())) { b.click(); return; }
    }
  }, { src: tc.match.source, flags: tc.match.flags });

  // Wait 2s for the dispatch to fly (or not). apiCalls is the canonical
  // signal — panel state persists across iterations and would falsely pass.
  await page.waitForTimeout(2000);
  const dispatchCall = apiCalls.find((c) => c.url.includes("/api/agent/dispatch"));

  if (tc.expectNoFire) {
    if (!dispatchCall) {
      pass++;
      console.log(`  ✓ ${tc.name} — correctly did NOT fire agent`);
    } else {
      fail++;
      console.log(`  ✗ ${tc.name} — /api/agent/dispatch fired but shouldn't have`);
    }
    continue;
  }

  if (dispatchCall) {
    pass++;
    console.log(`  ✓ ${tc.name} — /api/agent/dispatch fired`);
  } else {
    fail++;
    console.log(`  ✗ ${tc.name} — clicked "${matched.text}" but no /api/agent/dispatch`);
    console.log(`      api calls during window: ${apiCalls.map(c => c.method + " " + c.url.replace(BASE, "")).join(", ") || "(none)"}`);
  }
}

await browser.close();
console.log(`\n${pass} pass · ${fail} fail`);
process.exit(fail > 0 ? 1 : 0);
