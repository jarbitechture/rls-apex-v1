#!/usr/bin/env node
// Fetch remaining fixtures: mymanatee calendar + FL AG opinion.
// Uses Playwright for JS rendering.

import { chromium } from 'playwright';
import { writeFile, mkdir } from 'fs/promises';
import { dirname } from 'path';

const TARGETS = [
  // Try multiple mymanatee.org URLs for the holidays/calendar page
  {
    candidates: [
      'https://www.mymanatee.org/departments/financial_management/human_resources/county_holidays',
      'https://www.mymanatee.org/departments/financial_management/human_resources',
      'https://www.mymanatee.org/government/board_of_county_commissioners',
      'https://www.mymanatee.org/calendar',
    ],
    out: 'tests/services/scraper/fixtures/mymanatee_calendar_2026.html',
    label: 'mymanatee_calendar',
    contentPattern: /\b(holiday|new year|christmas|thanksgiving|memorial day|labor day)\b/i,
  },
  // FL AG opinions index
  {
    candidates: [
      'https://www.myfloridalegal.com/legal-opinions',
      'https://www.myfloridalegal.com/opinions',
      'https://myfloridalegal.com/legal-opinions',
    ],
    out: 'tests/services/scraper/fixtures/fl_ag_opinion_sample.html',
    label: 'fl_ag_opinion',
    // Look for ANY individual opinion link, then navigate to it
    sectionLinkSelector: 'a[href*="opinion"][href*="20"]',
    contentPattern: /\b(attorney general|opinion|fla\. op\. att|advisory)\b/i,
  },
];

const BROWSER_ARGS = {
  headless: true,
  args: ['--no-sandbox', '--disable-blink-features=AutomationControlled'],
};

async function tryCandidates(page, target) {
  for (const url of target.candidates) {
    try {
      console.log(`[${target.label}] trying ${url}`);
      const resp = await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
      await page.waitForTimeout(3000);

      const status = resp ? resp.status() : 0;
      const text = (await page.textContent('body').catch(() => '')) || '';
      const isNotFound = /404|page not found|cortez/i.test(text) && text.length < 3000;

      console.log(`[${target.label}]   status=${status}, length=${text.length}, isNotFound=${isNotFound}`);

      if (status === 200 && !isNotFound && target.contentPattern && target.contentPattern.test(text)) {
        console.log(`[${target.label}]   ✓ candidate matches pattern`);
        return url;
      } else {
        console.log(`[${target.label}]   ✗ candidate rejected (pattern not found)`);
      }
    } catch (err) {
      console.log(`[${target.label}]   error: ${err.message}`);
    }
  }
  return null;
}

async function scrape(page, target) {
  console.log(`\n[${target.label}] testing candidates...`);
  const winnerUrl = await tryCandidates(page, target);

  if (!winnerUrl) {
    console.error(`[${target.label}] NO CANDIDATE URL MATCHED — skipping`);
    return false;
  }

  // For FL AG, drill one level deeper to find a specific opinion
  if (target.sectionLinkSelector) {
    console.log(`[${target.label}] drilling into specific opinion via selector ${target.sectionLinkSelector}`);
    const links = await page.$$eval(target.sectionLinkSelector, (els) =>
      els.slice(0, 30).map((e) => ({ href: e.getAttribute('href'), text: e.textContent.trim().slice(0, 80) }))
    );

    console.log(`[${target.label}] found ${links.length} candidate links:`);
    links.slice(0, 5).forEach((l) => console.log(`    - ${l.text || '(no text)'} → ${l.href?.slice(0, 100)}`));

    if (links.length > 0) {
      const target_link = links.find((l) => l.href && /20\d{2}-\d+|opinion[s]?\/\d{4}/i.test(l.href)) || links[0];
      if (target_link?.href) {
        const opinionUrl = target_link.href.startsWith('http')
          ? target_link.href
          : new URL(target_link.href, winnerUrl).toString();
        console.log(`[${target.label}] navigating to specific opinion: ${opinionUrl}`);
        await page.goto(opinionUrl, { waitUntil: 'networkidle', timeout: 30000 });
        await page.waitForTimeout(3000);
      }
    }
  }

  const html = await page.content();
  await mkdir(dirname(target.out), { recursive: true });
  await writeFile(target.out, html, 'utf-8');

  const sizeKB = (html.length / 1024).toFixed(1);
  console.log(`[${target.label}] wrote ${target.out} (${sizeKB} KB)`);

  // Sample paragraphs
  const sampleP = await page.$$eval('p, .field-item, .opinion-content', (ps) =>
    ps.map((p) => p.textContent.trim()).filter((t) => t.length > 30).slice(0, 3)
  );
  console.log(`[${target.label}] sample paragraphs:`);
  sampleP.forEach((t) => console.log(`    - ${t.slice(0, 120)}`));

  return true;
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
