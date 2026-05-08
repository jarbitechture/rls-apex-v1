import { test, expect } from 'vitest';
import { computeSuggestions, RULES } from '../../static/core/automation/auto-correct.js';

test('subject-trim suggests when title > 50 chars', () => {
  const payload = { title: 'A'.repeat(60), legalQuestion: '', factualBackground: '' };
  const out = computeSuggestions(payload);
  const trim = out.find(s => s.ruleId === 'subject-trim');
  expect(trim).toBeDefined();
  expect(trim.field).toBe('title');
  expect(trim.proposedValue.length).toBeLessThanOrEqual(50);
});

test('subject-trim does not fire when title <= 50 chars', () => {
  const payload = { title: 'short title', legalQuestion: '', factualBackground: '' };
  expect(computeSuggestions(payload).find(s => s.ruleId === 'subject-trim')).toBeUndefined();
});

test('title-case-fix proposes Title Case for ALLCAPS words >3ch', () => {
  const payload = { title: 'NEEDS REVIEW for parcel', legalQuestion: '', factualBackground: '' };
  const out = computeSuggestions(payload).find(s => s.ruleId === 'title-case-fix');
  expect(out).toBeDefined();
  expect(out.proposedValue).toBe('Needs Review for parcel');
});

test('date-infer fires on relative date words', () => {
  const payload = { title: '', legalQuestion: '', factualBackground: 'Yesterday the NOV was issued' };
  const out = computeSuggestions(payload).find(s => s.ruleId === 'date-infer');
  expect(out).toBeDefined();
  expect(out.field).toBe('factualBackground');
});

test('all rules check returns empty for clean payload', () => {
  const payload = { title: 'Clean Title', legalQuestion: 'Question', factualBackground: 'Specific date Jan 5 2026' };
  expect(computeSuggestions(payload)).toEqual([]);
});
