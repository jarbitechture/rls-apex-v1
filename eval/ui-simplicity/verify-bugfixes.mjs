// verify-bugfixes.mjs — empirical check of the two bug reports:
//  1. Land Use & Public Records routes render distinct content (lens filter)
//  2. Policy Graph nodes are clickable and the right rail updates
import { chromium } from "playwright";

const BASE = process.env.RLS_BASE || "http://127.0.0.1:8080";
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();

await page.goto(`${BASE}/?ui_simplicity=1`, { waitUntil: "networkidle" });
await page.waitForFunction(() => typeof window.__RLS_GO === "function", null, { timeout: 8000 });

let pass = 0, fail = 0;

// ── 1. LU vs PR distinct content ────────────────────────────────────
await page.evaluate(() => window.__RLS_ROUTE_SET("lu"));
await page.waitForTimeout(400);
const luTitle = await page.evaluate(() => {
  const h = document.querySelector("h1, h2, h3"); return h && h.textContent.trim();
});
const luFooter = await page.evaluate(() => (document.body.textContent.match(/(\d+) of (\d+) matters/) || [])[0]);

await page.evaluate(() => window.__RLS_ROUTE_SET("pr"));
await page.waitForTimeout(400);
const prTitle = await page.evaluate(() => {
  const h = document.querySelector("h1, h2, h3"); return h && h.textContent.trim();
});
const prFooter = await page.evaluate(() => (document.body.textContent.match(/(\d+) of (\d+) matters/) || [])[0]);

if (luTitle && prTitle && luTitle !== prTitle && luFooter !== prFooter) {
  pass++;
  console.log(`  ✓ LU vs PR distinct — LU: "${luTitle}" (${luFooter}), PR: "${prTitle}" (${prFooter})`);
} else {
  fail++;
  console.log(`  ✗ LU vs PR same — LU: "${luTitle}" (${luFooter}), PR: "${prTitle}" (${prFooter})`);
}

// ── 2. Policy Graph node click updates SELECTED ─────────────────────
await page.evaluate(() => window.__RLS_ROUTE_SET("policy"));
await page.waitForTimeout(400);

const initialSelected = await page.evaluate(() => {
  // SELECTED title is the .serif span right after "SELECTED"
  const labels = Array.from(document.querySelectorAll(".mono"))
    .filter(el => el.textContent.trim() === "SELECTED");
  if (!labels.length) return null;
  const sib = labels[0].nextElementSibling;
  return sib ? sib.textContent.trim() : null;
});

// Click a different node — preempt (§163.31801)
await page.evaluate(() => {
  const node = document.querySelector('g[data-rls-node="preempt"]');
  if (node) node.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
});
await page.waitForTimeout(300);

const afterSelected = await page.evaluate(() => {
  const labels = Array.from(document.querySelectorAll(".mono"))
    .filter(el => el.textContent.trim() === "SELECTED");
  if (!labels.length) return null;
  const sib = labels[0].nextElementSibling;
  return sib ? sib.textContent.trim() : null;
});

if (initialSelected && afterSelected && initialSelected !== afterSelected) {
  pass++;
  console.log(`  ✓ Policy node click works — initial="${initialSelected}" → after="${afterSelected}"`);
} else {
  fail++;
  console.log(`  ✗ Policy node click stuck — initial="${initialSelected}" → after="${afterSelected}"`);
}

await browser.close();
console.log(`\n${pass} pass · ${fail} fail`);
process.exit(fail > 0 ? 1 : 0);
