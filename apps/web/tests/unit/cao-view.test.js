import { test, expect, vi } from 'vitest';
import '../../static/components/cao-view.js';

test('fetches /api/cao/brief on connect and renders bullets', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true, json: async () => ({
      rlsId: 'RLS-25-067',
      summary: ['s1', 's2', 's3'],
      keyFacts: ['k1'],
      risk: 'risk text',
      suggestedNextSteps: ['step1'],
    }),
  })));
  const el = document.createElement('cao-view');
  el.rlsId = 'RLS-25-067';
  document.body.appendChild(el);
  await new Promise(r => setTimeout(r, 30));
  await el.updateComplete;
  expect(el.shadowRoot.textContent).toMatch(/s1.*s2.*s3/s);
  expect(el.shadowRoot.textContent).toMatch(/risk text/);
});

test('decision buttons render and clicking shows toast', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({
    rlsId: 'X', summary: [], keyFacts: [], risk: '', suggestedNextSteps: [],
  }) })));
  const el = document.createElement('cao-view');
  el.rlsId = 'X';
  document.body.appendChild(el);
  await new Promise(r => setTimeout(r, 30));
  await el.updateComplete;
  const accept = [...el.shadowRoot.querySelectorAll('button')].find(b => b.textContent.includes('Accept'));
  accept.click();
  await el.updateComplete;
  expect(el.shadowRoot.textContent).toMatch(/v0\.2\.1/);
});
