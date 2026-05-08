import { test, expect, vi, beforeEach } from 'vitest';
import * as api from '../../static/core/api.js';

beforeEach(() => { vi.restoreAllMocks(); });

test('fetchMe returns parsed json', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true, json: async () => ({ upn: 'a@b.com', role: 'requester', dept: 'DEV', role_band: 'professional' }),
  }));
  const me = await api.fetchMe();
  expect(me.upn).toBe('a@b.com');
});

test('postIntake passes the body and parses response', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true, json: async () => ({ classification: { type: 'X' }, rlsPayload: {} }),
  }));
  const r = await api.postIntake({ text: 'permit denial' });
  expect(r.classification.type).toBe('X');
  const call = global.fetch.mock.calls[0];
  expect(call[0]).toBe('/api/intake');
  expect(JSON.parse(call[1].body).text).toBe('permit denial');
});

test('postValidate respects AbortSignal', async () => {
  const c = new AbortController();
  vi.stubGlobal('fetch', vi.fn().mockImplementation((_, opts) => {
    return new Promise((_, reject) => {
      opts.signal.addEventListener('abort', () => {
        const e = new Error('aborted'); e.name = 'AbortError'; reject(e);
      });
    });
  }));
  const p = api.postValidate({ rlsPayload: {} }, c.signal);
  c.abort();
  await expect(p).rejects.toThrow(/aborted/);
});
