import { LitElement, html, css } from 'lit';
import { fetchCaoBrief } from '../core/api.js';

export class CaoView extends LitElement {
  static properties = {
    rlsId: { type: String },
    _brief: { state: true },
    _err: { state: true },
    _toast: { state: true },
  };
  static styles = css`
    :host { display: block; max-width: 800px; padding: 24px; }
    h2 { color: var(--primary-ink, #036); }
    .section { margin: 16px 0; }
    .section h3 { margin-bottom: 6px; }
    ul { padding-left: 20px; }
    .actions { margin-top: 24px; display: flex; gap: 8px; }
    button.accept { background: var(--success, #2e7d32); color: white; }
    button.return { background: var(--warn, #b8861b); color: white; }
    button.reject { background: var(--err, #c0392b); color: white; }
    button.accept, button.return, button.reject { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; }
    .toast { position: fixed; bottom: 24px; right: 24px; padding: 12px 16px;
             background: var(--ink, #222); color: white; border-radius: 4px; }
  `;

  constructor() { super(); this._brief = null; this._err = null; this._toast = null; }

  async connectedCallback() {
    super.connectedCallback();
    try { this._brief = await fetchCaoBrief(this.rlsId); }
    catch (err) { this._err = String(err); }
  }

  _decision(kind) {
    this._toast = `${kind} — decision write goes live in v0.2.1`;
    setTimeout(() => { this._toast = null; }, 4000);
  }

  render() {
    if (this._err) return html`<p style="color:var(--err)">Failed to load brief: ${this._err}</p>`;
    if (!this._brief) return html`<p>Loading brief…</p>`;
    const b = this._brief;
    return html`
      <h2>${b.rlsId} — Brief for CAO Review</h2>
      <div class="section"><h3>Summary</h3><ul>${b.summary.map(s => html`<li>${s}</li>`)}</ul></div>
      <div class="section"><h3>Key facts</h3><ul>${b.keyFacts.map(s => html`<li>${s}</li>`)}</ul></div>
      <div class="section"><h3>Risk</h3><p>${b.risk}</p></div>
      <div class="section"><h3>Suggested next steps</h3>
        <ul>${b.suggestedNextSteps.map(s => html`<li>${s}</li>`)}</ul>
      </div>
      <div class="actions">
        ${['Accept', 'Return', 'Reject'].map(kind => html`
          <button class=${kind.toLowerCase()} disabled
                  title="CAO decision write goes live in v0.2.1 with update_rls_status"
                  @click=${() => this._decision(kind)}>${kind}</button>`)}
      </div>
      ${this._toast ? html`<div class="toast">${this._toast}</div>` : ''}
    `;
  }
}

customElements.define('cao-view', CaoView);
