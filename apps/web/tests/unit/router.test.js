import { test, expect, vi } from 'vitest';
import { parseLocation, navigateToStep } from '../../static/core/router.js';

test('parseLocation: root + #step=form returns step view', () => {
  const r = parseLocation({ pathname: '/static/index.html', hash: '#step=form' });
  expect(r).toEqual({ view: 'requester', step: 'form' });
});

test('parseLocation: /cao/X returns cao view with rlsId', () => {
  const r = parseLocation({ pathname: '/cao/RLS-25-067', hash: '' });
  expect(r).toEqual({ view: 'cao', rlsId: 'RLS-25-067' });
});

test('parseLocation: root with no hash defaults to intake step', () => {
  const r = parseLocation({ pathname: '/static/index.html', hash: '' });
  expect(r).toEqual({ view: 'requester', step: 'intake' });
});

test('navigateToStep updates location.hash', () => {
  const fakeLoc = { hash: '' };
  navigateToStep('form', fakeLoc);
  expect(fakeLoc.hash).toBe('#step=form');
});
