// screenshot-all.mjs — render every key route at 1440×900 and write
// to ~/Desktop/servo-screenshots/rls-apex-{route}.png. Used as an audit
// to confirm each surface actually renders (advisor's gap).
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

const BASE = process.env.RLS_BASE || "http://127.0.0.1:8080";
const OUT = join(homedir(), "Desktop", "servo-screenshots");
mkdirSync(OUT, { recursive: true });

const routes = [
  { route: "dashboard",   label: "Dashboard" },
  { route: "submissions", label: "Submissions" },
  { route: "wizard",      label: "Wizard" },
  { route: "inbox",       label: "Inbox" },
  { route: "drafts",      label: "Drafts" },
  { route: "ai",          label: "AI Co-pilot" },
  { route: "bie",         label: "BIE Worksheets" },
  { route: "ce",          label: "Code Enforcement" },
  { route: "lu",          label: "Land Use" },
  { route: "pr",          label: "Public Records" },
  { route: "policy",      label: "Policy Graph" },
  { route: "precedents",  label: "Precedents" },
  { route: "kpi",         label: "KPI Analytics" },
];

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();

await page.goto(`${BASE}/?ui_simplicity=1`, { waitUntil: "networkidle" });
await page.waitForFunction(() => typeof window.__RLS_GO === "function", null, { timeout: 8000 });

console.log(`route                file                                                      status   notes`);
console.log(`─`.repeat(110));
for (const { route, label } of routes) {
  const isDetail = route === "detail";
  if (route === "detail") {
    await page.evaluate(() => window.__RLS_GO("detail", "RLS-26-0141"));
  } else {
    await page.evaluate((r) => window.__RLS_ROUTE_SET(r), route);
  }
  await page.waitForTimeout(700);

  const stats = await page.evaluate(() => {
    const main = document.querySelector("main");
    if (!main) return { rendered: false, mainText: 0, headings: 0, buttons: 0 };
    const txt = (main.textContent || "").trim().length;
    const heads = main.querySelectorAll("h1, h2, h3").length;
    const btns = main.querySelectorAll("button").length;
    return { rendered: txt > 100, mainText: txt, headings: heads, buttons: btns };
  });

  const file = join(OUT, `rls-apex-${route}.png`);
  await page.screenshot({ path: file, fullPage: false });
  const status = stats.rendered ? "ok " : "BLANK";
  console.log(`${route.padEnd(20)} ${file.replace(homedir(), "~").padEnd(56)} ${status.padEnd(8)} text=${stats.mainText} heads=${stats.headings} btns=${stats.buttons}`);
}
await browser.close();
