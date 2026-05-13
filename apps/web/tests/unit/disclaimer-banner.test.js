import { test, expect, vi, beforeEach } from 'vitest';
import '../../static/components/rls-disclaimer-banner.js';
import '../../static/components/rls-shell.js';

beforeEach(() => {
  localStorage.clear();
  // Reset DOM between tests so document.querySelector doesn't see prior fixtures
  document.body.innerHTML = '';
});

test('renders the validator-framed disclaimer text', async () => {
  const el = document.createElement('rls-disclaimer-banner');
  document.body.appendChild(el);
  await el.updateComplete;
  const txt = el.shadowRoot.textContent;
  expect(txt).toMatch(/Grades a request-for-legal-services draft/);
  expect(txt).toMatch(/Does not provide legal advice/);
  expect(txt).toMatch(/Does not cite case law/);
});

test('sets data-testid on the host element (light DOM, queryable without shadow piercing)', async () => {
  const el = document.createElement('rls-disclaimer-banner');
  document.body.appendChild(el);
  await el.updateComplete;
  expect(el.getAttribute('data-testid')).toBe('rls-disclaimer-banner');
  // Also queryable via document selector
  expect(document.querySelector('[data-testid="rls-disclaimer-banner"]')).toBe(el);
});

test('sets accessibility attributes for screen readers', async () => {
  const el = document.createElement('rls-disclaimer-banner');
  document.body.appendChild(el);
  await el.updateComplete;
  expect(el.getAttribute('role')).toBe('note');
  expect(el.getAttribute('aria-label')).toBe('Legal disclaimer');
});

test('is not dismissible (no close button or dismiss control)', async () => {
  const el = document.createElement('rls-disclaimer-banner');
  document.body.appendChild(el);
  await el.updateComplete;
  expect(el.shadowRoot.querySelector('button')).toBeNull();
  expect(el.shadowRoot.querySelector('[aria-label="dismiss" i]')).toBeNull();
  expect(el.shadowRoot.querySelector('[aria-label="close" i]')).toBeNull();
});

test('rls-shell mounts the banner above the panel area in the requester view', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => ({
    ok: true,
    json: async () => ({ upn: 'a@b.com', role: 'requester', dept: 'DEV', role_band: 'professional', breakers: {} }),
  })));
  const shell = document.createElement('rls-shell');
  document.body.appendChild(shell);
  await new Promise(r => setTimeout(r, 50));
  await shell.updateComplete;
  const banner = shell.shadowRoot.querySelector('rls-disclaimer-banner');
  expect(banner).toBeTruthy();
  const layout = shell.shadowRoot.querySelector('.layout');
  expect(layout).toBeTruthy();
  // Banner must precede the panel area (.layout) in document order.
  const rel = banner.compareDocumentPosition(layout);
  expect(rel & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
});
