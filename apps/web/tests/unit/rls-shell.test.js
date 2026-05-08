import { test, expect, vi, beforeEach } from 'vitest';
import '../../static/components/rls-shell.js';

beforeEach(() => { localStorage.clear(); });

test('connectedCallback hydrates store and queries /api/me', async () => {
  vi.stubGlobal('fetch', vi.fn(async (url) => {
    if (url === '/api/me') return { ok: true, json: async () => ({ upn: 'a@b.com', role: 'requester', dept: 'DEV', role_band: 'professional' }) };
    if (url === '/api/health/breakers') return { ok: true, json: async () => ({ breakers: {} }) };
    throw new Error('unexpected fetch ' + url);
  }));
  const el = document.createElement('rls-shell');
  document.body.appendChild(el);
  await new Promise(r => setTimeout(r, 50));
  expect(el.store.session.upn).toBe('a@b.com');
});

test('renders the requester view by default', async () => {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => ({ upn: 'a@b.com', role: 'requester', dept: 'DEV', role_band: 'professional', breakers: {} }) })));
  const el = document.createElement('rls-shell');
  document.body.appendChild(el);
  await new Promise(r => setTimeout(r, 50));
  await el.updateComplete;
  expect(el.shadowRoot.querySelector('app-header')).toBeTruthy();
  expect(el.shadowRoot.querySelector('step-bar')).toBeTruthy();
});
