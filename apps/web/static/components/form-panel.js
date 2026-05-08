import { LitElement, html, css } from 'lit';
import { navigateToStep } from '../core/router.js';

const FIELDS = ['title', 'department', 'legalQuestion', 'factualBackground'];

export class FormPanel extends LitElement {
  static properties = {
    store: { attribute: false },
    surface: { attribute: false },
    _ver: { state: true },
  };
  static styles = css`
    :host { display: block; max-width: 720px; }
    .field { margin: 12px 0; }
    label { display: block; font-size: 13px; color: var(--ink-2, #444); }
    input, textarea { width: 100%; padding: 6px 8px; font: inherit;
                      border: 1px solid var(--muted-2, #ccc); border-radius: 4px; }
    textarea { min-height: 80px; }
    .err { color: var(--err, #c0392b); font-size: 12px; margin-top: 4px; }
    .chip { display: inline-flex; gap: 8px; align-items: center; padding: 4px 8px;
            background: var(--warn-bg, #fff8e1); border: 1px solid var(--warn, #b8861b);
            border-radius: 4px; margin-top: 4px; font-size: 12px; }
    .chip button { padding: 2px 8px; font-size: 12px; cursor: pointer; }
    .actions { margin-top: 16px; display: flex; gap: 8px; }
    button.primary { padding: 8px 16px; background: var(--primary, #036); color: white;
                     border: none; border-radius: 4px; cursor: pointer; }
    button.secondary { padding: 8px 16px; background: var(--canvas, #fff); color: var(--ink, #111);
                       border: 1px solid var(--muted-2, #ccc); border-radius: 4px; cursor: pointer; }
  `;

  connectedCallback() {
    super.connectedCallback();
    this._u1 = this.store?.subscribe('draft', () => { this._ver = (this._ver || 0) + 1; });
    this._u2 = this.store?.subscribe('ui', () => { this._ver = (this._ver || 0) + 1; });
  }
  disconnectedCallback() { super.disconnectedCallback(); this._u1?.(); this._u2?.(); }

  _onInput(field, value) { this.store.update('draft', d => { d.rlsPayload[field] = value; }); }
  _onBlur(field) { this.store.update('ui', u => { u.blurredFields.add(field); }); }
  _applySuggestion(suggestion) {
    this.store.update('draft', d => { d.rlsPayload[suggestion.field] = suggestion.proposedValue; });
    this.store.update('ui', u => { u.autocorrectSuggestions = u.autocorrectSuggestions.filter(s => s !== suggestion); });
  }
  _dismiss(suggestion) {
    this.store.update('ui', u => { u.autocorrectSuggestions = u.autocorrectSuggestions.filter(s => s !== suggestion); });
  }

  render() {
    const payload = this.store?.draft.rlsPayload ?? {};
    const fieldErrors = this.surface?.fieldErrors ?? {};
    const suggestions = this.store?.ui.autocorrectSuggestions ?? [];
    return html`
      <h2>Step 2 — Form</h2>
      ${FIELDS.map(f => {
        const fSugs = suggestions.filter(s => s.field === f);
        const isLong = f === 'legalQuestion' || f === 'factualBackground';
        const inputEl = isLong
          ? html`<textarea data-field=${f} .value=${payload[f] ?? ''}
                  @input=${e => this._onInput(f, e.target.value)} @blur=${() => this._onBlur(f)}></textarea>`
          : html`<input data-field=${f} .value=${payload[f] ?? ''}
                  @input=${e => this._onInput(f, e.target.value)} @blur=${() => this._onBlur(f)}>`;
        return html`
          <div class="field">
            <label>${f}</label>
            ${inputEl}
            ${fieldErrors[f] ? html`<div class="err">${fieldErrors[f]}</div>` : ''}
            ${fSugs.map(s => html`
              <div class="chip">
                ${s.reason}: <em>${s.proposedValue.length > 60 ? s.proposedValue.slice(0,60)+'…' : s.proposedValue}</em>
                <button @click=${() => this._applySuggestion(s)}>Apply</button>
                <button @click=${() => this._dismiss(s)}>Dismiss</button>
              </div>
            `)}
          </div>
        `;
      })}
      <div class="actions">
        <button class="secondary" @click=${() => navigateToStep('intake')}>← Back</button>
        <button class="primary" @click=${() => navigateToStep('status')}>Next → Status</button>
      </div>
    `;
  }
}

customElements.define('form-panel', FormPanel);
