import { LitElement, html, css } from 'lit';
import { createStore } from '../core/store.js';
import { hydrate, attachAutoSave } from '../core/persist.js';
import * as api from '../core/api.js';
import { attachRouter, parseLocation } from '../core/router.js';
import { attachValidatorRunner } from '../core/automation/validator-runner.js';
import { attachAutoCorrect } from '../core/automation/auto-correct.js';
import { attachSmartSurface } from '../core/automation/smart-surface.js';

import './app-header.js';
import './step-bar.js';
import './intake-panel.js';
import './form-panel.js';
import './status-panel.js';
import './cure-path-panel.js';
import './submit-panel.js';
import './copilot-feed.js';
import './cao-view.js';

const BREAKER_POLL_MS = 30_000;

export class RlsShell extends LitElement {
  static properties = {
    _ready: { state: true },
    _surface: { state: true },
    _route: { state: true },
  };

  static styles = css`
    :host { display: block; min-height: 100vh; background: var(--canvas, #fff); color: var(--ink, #111); }
    .layout { display: grid; grid-template-columns: 1fr 280px; gap: 16px; padding: 16px; }
    .main { min-height: 60vh; }
  `;

  constructor() {
    super();
    this._ready = false;
    this._surface = { fieldErrors: {}, banners: [] };
    this._route = { view: 'requester', step: 'intake' };
    this.store = createStore();
  }

  async connectedCallback() {
    super.connectedCallback();
    try {
      const me = await api.fetchMe();
      this.store.session.upn = me.upn;
      this.store.session.role = me.role || 'requester';
    } catch (err) {
      this.store.update('errorState', e => { e.lastApiError = `me: ${err}`; });
    }

    hydrate(this.store);
    attachAutoSave(this.store);
    attachRouter(this.store);
    attachValidatorRunner(this.store, { postValidate: api.postValidate });
    attachAutoCorrect(this.store);
    attachSmartSurface(this.store, surface => { this._surface = surface; this.requestUpdate(); });

    this._route = parseLocation();
    window.addEventListener('hashchange', () => { this._route = parseLocation(); });
    window.addEventListener('popstate', () => { this._route = parseLocation(); });

    this._pollBreakers();
    this._ready = true;
  }

  async _pollBreakers() {
    try {
      const r = await api.fetchBreakers();
      this.store.update('errorState', e => { e.breakerStatus = r.breakers || {}; });
    } catch { /* silent — banner via smart-surface picks it up if needed */ }
    setTimeout(() => this._pollBreakers(), BREAKER_POLL_MS);
  }

  render() {
    if (!this._ready) return html`<p style="padding:32px;color:var(--ink-3)">Loading…</p>`;
    if (this._route.view === 'cao') return html`<cao-view .rlsId=${this._route.rlsId}></cao-view>`;
    return html`
      <app-header .store=${this.store} .surface=${this._surface}></app-header>
      <step-bar .store=${this.store}></step-bar>
      <div class="layout">
        <div class="main">${this._renderStep()}</div>
        <copilot-feed .store=${this.store}></copilot-feed>
      </div>
    `;
  }

  _renderStep() {
    const step = this.store.session.currentStep;
    switch (step) {
      case 'intake':  return html`<intake-panel  .store=${this.store}></intake-panel>`;
      case 'form':    return html`<form-panel    .store=${this.store} .surface=${this._surface}></form-panel>`;
      case 'status':  return html`<status-panel  .store=${this.store} .surface=${this._surface}></status-panel>`;
      case 'cure':    return html`<cure-path-panel .store=${this.store}></cure-path-panel>`;
      case 'submit':  return html`<submit-panel  .store=${this.store}></submit-panel>`;
      default:        return html`<p>Unknown step: ${step}</p>`;
    }
  }
}

customElements.define('rls-shell', RlsShell);
