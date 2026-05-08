import { LitElement, html, css } from 'lit';
import { navigateToStep } from '../core/router.js';

export class StatusPanel extends LitElement {
  static properties = { store: { attribute: false }, surface: { attribute: false }, _ver: { state: true } };
  static styles = css`
    :host { display: block; max-width: 720px; }
    .narrative { font-size: 18px; padding: 12px 0; }
    .narrative.fixes { color: var(--err, #c0392b); }
    .narrative.ready { color: var(--success, #2e7d32); }
    h3 { margin-top: 24px; }
    ul { padding-left: 20px; }
    li.block { color: var(--err, #c0392b); }
    li.warn { color: var(--warn, #b8861b); }
    .actions { margin-top: 24px; display: flex; gap: 8px; }
    button { padding: 8px 16px; border-radius: 4px; cursor: pointer; }
    .primary { background: var(--primary, #036); color: white; border: none; }
    .secondary { background: var(--canvas, #fff); border: 1px solid var(--muted-2, #ccc); }
    .stale { color: var(--ink-3, #777); font-size: 13px; }
  `;

  connectedCallback() {
    super.connectedCallback();
    this._u = this.store?.subscribe('draft', () => { this._ver = (this._ver || 0) + 1; });
  }
  disconnectedCallback() { super.disconnectedCallback(); this._u?.(); }

  render() {
    const blocking = this.store?.draft.blocking ?? [];
    const warnings = this.store?.draft.warnings ?? [];
    const last = this.store?.draft.lastValidated;
    const status = blocking.length === 0 && last ? 'ready' : 'fixes';
    return html`
      <h2>Step 3 — Status</h2>
      <div class="narrative ${status}">
        ${status === 'ready'
          ? `Status: Ready for CAO review — all required checks passed.`
          : `Status: Needs fixes before CAO review — ${blocking.length} required item${blocking.length === 1 ? '' : 's'} missing.`}
      </div>
      ${last ? '' : html`<div class="stale">Not yet validated. Edit the form, then return here.</div>`}
      ${blocking.length > 0 ? html`
        <h3>Blocking</h3>
        <ul>${blocking.map(b => html`<li class="block">${b.message ?? b.code}</li>`)}</ul>
      ` : ''}
      ${warnings.length > 0 ? html`
        <h3>Warnings</h3>
        <ul>${warnings.map(w => html`<li class="warn">${w.message ?? w.code}</li>`)}</ul>
      ` : ''}
      <div class="actions">
        <button class="secondary" @click=${() => navigateToStep('form')}>← Back to Form</button>
        ${blocking.length > 0
          ? html`<button class="primary" @click=${() => navigateToStep('cure')}>Cure path →</button>`
          : html`<button class="primary" @click=${() => navigateToStep('submit')}>Submit →</button>`}
      </div>
    `;
  }
}

customElements.define('status-panel', StatusPanel);
