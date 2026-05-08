import { test, expect } from 'vitest';
import '../../static/components/step-bar.js';
import { createStore } from '../../static/core/store.js';

test('renders 5 steps with currentStep highlighted', async () => {
  const store = createStore();
  store.session.currentStep = 'form';
  const el = document.createElement('step-bar');
  el.store = store;
  document.body.appendChild(el);
  await el.updateComplete;
  const items = el.shadowRoot.querySelectorAll('.step');
  expect(items.length).toBe(5);
  const active = el.shadowRoot.querySelector('.step.current');
  expect(active.textContent).toMatch(/Form/);
});

test('clicking a step updates the route via location.hash', async () => {
  const store = createStore();
  store.session.currentStep = 'intake';
  const el = document.createElement('step-bar');
  el.store = store;
  document.body.appendChild(el);
  await el.updateComplete;
  const formStep = [...el.shadowRoot.querySelectorAll('.step')].find(s => s.textContent.match(/Form/));
  formStep.click();
  expect(window.location.hash).toBe('#step=form');
});
