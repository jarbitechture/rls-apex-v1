import { LitElement, html, css } from 'lit';
import { postIntake } from '../core/api.js';
import { navigateToStep } from '../core/router.js';

const STRUCTURED_FIELDS = ['title', 'department', 'legalQuestion', 'factualBackground'];

export class IntakePanel extends LitElement {
  static properties = {
    store: { attribute: false },
    _text: { state: true },
    _skip: { state: true },
    _pending: { state: true },
    _err: { state: true },
  };
  static styles = css`
    :host { display: block; max-width: 720px; }
    textarea { width: 100%; min-height: 160px; font: inherit; padding: 8px;
               border: 1px solid var(--muted-2, #ccc); border-radius: 4px; }
    .row { margin: 12px 0; }
    label.toggle { display: flex; gap: 8px; align-items: center; cursor: pointer; }
    button.primary { padding: 8px 16px; background: var(--primary, #036); color: white;
                     border: none; border-radius: 4px; cursor: pointer; }
    button.primary:disabled { opacity: 0.5; cursor: not-allowed; }
    .err { color: var(--err, #c0392b); margin-top: 8px; }
    input[data-field] { width: 100%; padding: 6px 8px; margin-top: 4px;
                        border: 1px solid var(--muted-2, #ccc); border-radius: 4px; }
  `;

  constructor() { super(); this._text = ''; this._skip = false; this._pending = false; this._err = null; }

  _setField(field, value) {
    this.store.update('draft', d => { d.rlsPayload[field] = value; });
  }

  async _draft() {
    this._pending = true; this._err = null;
    try {
      const r = await postIntake({ text: this._text });
      this.store.update('draft', d => {
        Object.assign(d.rlsPayload, r.rlsPayload || {});
        if (r.classification) d.classification = r.classification;
        if (!d.rlsId) d.rlsId = `rls-${crypto.randomUUID()}`;
      });
      this.store.update('session', s => {
        s.eventLog.push({ ts: Date.now(), tool: 'classify_matter', summary: r.classification?.type ?? 'unknown' });
      });
      navigateToStep('form');
    } catch (err) {
      this._err = String(err);
    } finally {
      this._pending = false;
    }
  }

  render() {
    const payload = this.store?.draft.rlsPayload ?? {};
    return html`
      <h2>Step 1 — Intake</h2>
      <p>Describe the situation and what you're asking CAO to do.</p>
      <div class="row">
        <label class="toggle">
          <input type="checkbox" .checked=${this._skip} @change=${e => { this._skip = e.target.checked; }}>
          Skip — I have a draft already
        </label>
      </div>
      ${this._skip ? html`
        ${STRUCTURED_FIELDS.map(f => html`
          <div class="row">
            <label>${f}</label>
            <input data-field=${f} .value=${payload[f] ?? ''} @input=${e => this._setField(f, e.target.value)}>
          </div>
        `)}
        <button class="primary" @click=${() => navigateToStep('form')}>Continue → Form</button>
      ` : html`
        <textarea .value=${this._text} @input=${e => { this._text = e.target.value; }}
                  placeholder="Need legal review on a permit denial for parcel 12345..."></textarea>
        <div class="row">
          <button class="primary" .disabled=${this._pending || this._text.trim().length < 10} @click=${this._draft}>
            ${this._pending ? 'Drafting…' : 'Draft RLS'}
          </button>
        </div>
        ${this._err ? html`<div class="err">${this._err}</div>` : ''}
      `}
    `;
  }
}

customElements.define('intake-panel', IntakePanel);
