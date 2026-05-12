#!/usr/bin/env node
// Scrape JS-rendered fixtures for v0.2.1a Plan A Tasks 6-7.
// Uses Playwright (installed in node_modules).
//
// Strategy:
//   1. Navigate to LDC root (no nodeId — landing page).
//   2. Wait for Angular TOC to mount.
//   3. Find first valid section link, navigate to it.
//   4. Capture the section's rendered HTML.
//   5. Repeat for Code of Ordinances Ch. 2-26 root.
//
// Outputs:
//   tests/services/scraper/fixtures/municode_ldc_section_6_4.html  (current first-section)
//   tests/services/scraper/fixtures/municode_ch2_26_section.html

import { chromium } from 'playwright';
import { writeFile, mkdir } from 'fs/promises';
import { dirname } from 'path';

const TARGETS = [
  {
    rootUrl: 'https://library.municode.com/fl/manatee_county/codes/land_development_code',
    out: 'tests/services/scraper/fixtures/municode_ldc_section_6_4.html',
    label: 'municode_ldc',
    // Search the TOC for the first deep-leaf link (skip parts/chapters)
    sectionLinkSelector: 'a[href*="nodeId="][href*="_"]:not(:has(.fa-chevron-right))',
  },
  {
    rootUrl: 'https://library.municode.com/fl/manatee_county/codes/code_of_ordinances?nodeId=PTIIMACOCOOR_CH2-26MACOPROR',
    out: 'tests/services/scraper/fixtures/municode_ch2_26_section.html',
    label: 'municode_ch2_26',
    sectionLinkSelector: 'a[href*="nodeId="][href*="_"]:not(:has(.fa-chevron-right))',
  },
];

const BROWSER_ARGS = {
  headless: true,
  args: ['--no-sandbox', '--disable-blink-features=AutomationControlled'],
};

async function findValidSection(page, label) {
  // Wait for TOC root to mount
  await page.waitForTimeout(5000);

  // Try to find any link with a nodeId param — those are TOC entries
  const links = await page.$$eval('a[href*="nodeId="]', (els) =>
    els.map((e) => ({ href: e.getAttribute('href'), text: e.textContent.trim().slice(0, 80) }))
  );

  console.log(`[${label}] found ${links.length} nodeId-bearing links in TOC`);
  if (links.length > 0) {
    console.log(`[${label}] sample first 5:`);
    links.slice(0, 5).forEach((l) => console.log(`    - ${l.text || '(no text)'} → ${l.href.slice(0, 100)}`));
  }
  return links;
}

async function scrape(page, target) {
  console.log(`\n[${target.label}] navigating to root: ${target.rootUrl}`);
  await page.goto(target.rootUrl, { waitUntil: 'networkidle', timeout: 60000 });
  console.log(`[${target.label}] DOM loaded; waiting for Angular TOC...`);

  // Wait for Angular digest cycle
  await page.waitForTimeout(8000);

  // Step 1: find a valid section link from the TOC
  const links = await findValidSection(page, target.label);

  // Step 2: pick a likely leaf (one that doesn't look like a chapter/part header)
  // Heuristic: text contains a section number like "6.4", "2-26-12", or "Sec. X"
  const leaf = links.find((l) =>
    /\b(sec\.|§|\d+[\.-]\d)/i.test(l.text) && !/\b(part|article|division|chapter)\b/i.test(l.text)
  ) || links.find((l) => l.text && l.text.length > 5) || links[0];

  if (!leaf) {
    throw new Error(`[${target.label}] no valid nodeId links found in TOC — site may have changed`);
  }

  console.log(`[${target.label}] picked: ${leaf.text} → ${leaf.href.slice(0, 100)}`);

  // Build absolute URL
  const sectionUrl = leaf.href.startsWith('http')
    ? leaf.href
    : new URL(leaf.href, target.rootUrl).toString();

  console.log(`[${target.label}] navigating to section: ${sectionUrl}`);
  await page.goto(sectionUrl, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(5000);

  // Sanity check: page should have actual section content
  const sampleP = await page.$$eval('p', (ps) =>
    ps.map((p) => p.textContent.trim()).filter((t) => t.length > 30).slice(0, 3)
  );
  console.log(`[${target.label}] sample paragraphs after navigation:`);
  sampleP.forEach((t) => console.log(`    - ${t.slice(0, 100)}`));

  const html = await page.content();
  await mkdir(dirname(target.out), { recursive: true });
  await writeFile(target.out, html, 'utf-8');

  const sizeKB = (html.length / 1024).toFixed(1);
  console.log(`[${target.label}] wrote ${target.out} (${sizeKB} KB)`);
}

async function main() {
  const browser = await chromium.launch(BROWSER_ARGS);
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();

  for (const target of TARGETS) {
    try {
      await scrape(page, target);
    } catch (err) {
      console.error(`[${target.label}] FAILED:`, err.message);
    }
  }

  await browser.close();
  console.log('\ndone');
}

main().catch((err) => {
  console.error('fatal:', err);
  process.exit(1);
});
