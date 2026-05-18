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

// GAP-2 (#41 parity audit, Option A): no production decision-write endpoint
// exists, so the CAO action buttons must follow the app's deferral pattern
// (disabled + v0.2.1 tooltip, like submit-panel / cure-path Mark Done)
// instead of looking actionable but only toasting.
test('decision buttons are disabled with a v0.2.1 deferral tooltip (no toast on click)', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({
    rlsId: 'X', summary: [], keyFacts: [], risk: '', suggestedNextSteps: [],
  }) })));
  const el = document.createElement('cao-view');
  el.rlsId = 'X';
  document.body.appendChild(el);
  await new Promise(r => setTimeout(r, 30));
  await el.updateComplete;

  const btns = [...el.shadowRoot.querySelectorAll('button')]
    .filter(b => /Accept|Return|Reject/.test(b.textContent));
  expect(btns).toHaveLength(3);
  for (const b of btns) {
    expect(b.disabled).toBe(true);
    expect(b.title).toMatch(/v0\.2\.1/);
  }
  // A disabled button does not dispatch click → no toast appears.
  btns[0].click();
  await el.updateComplete;
  expect(el.shadowRoot.querySelector('.toast')).toBeNull();
});
