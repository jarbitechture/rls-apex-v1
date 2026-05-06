// Drive a real Validate flow + capture screenshot for visual verification.
import { chromium } from "playwright";
import { join } from "node:path";
import { homedir } from "node:os";

const BASE = process.env.RLS_BASE || "http://127.0.0.1:8090";
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await ctx.newPage();

await page.goto(`${BASE}/?ui_simplicity=1`, { waitUntil: "networkidle" });
await page.waitForFunction(() => typeof window.__RLS_GO === "function", null, { timeout: 8000 });

// Type a sole-source query, click Validate, wait for the score block to render
await page.fill("textarea", "Can the County contract a sole-source IT vendor under §125.65 if findings are drafted concurrently?");
// Click the actual primary "Validate" button, not the sidebar nav-item.
await page.click("main button:has-text('Validate')");
await page.waitForFunction(
  () => /Rejection probability/i.test(document.body.textContent || ""),
  null, { timeout: 20000 },
).catch(() => {});
await page.waitForTimeout(6000); // let the answer + citations finish streaming
// scroll the result into view
await page.evaluate(() => {
  const main = document.querySelector("main");
  if (main) main.scrollTop = 0;
});

const out = join(homedir(), "Desktop", "servo-screenshots", "validate-pilot-fit.png");
await page.screenshot({ path: out, fullPage: false });
console.log(`screenshot -> ${out}`);
await browser.close();
