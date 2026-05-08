import { LitElement, html, css } from 'lit';
import { ALL_STEPS, navigateToStep } from '../core/router.js';

const LABELS = { intake: '1 Intake', form: '2 Form', status: '3 Status', cure: '4 Cure', submit: '5 Submit' };

export class StepBar extends LitElement {
  static properties = { store: { attribute: false }, _ver: { state: true } };
  static styles = css`
    :host { display: block; }
    .bar { display: flex; gap: 8px; padding: 8px 16px; background: var(--muted, #f5f5f5);
           border-bottom: 1px solid var(--muted-2, #ddd); }
    .step { padding: 6px 14px; border: 1px solid var(--muted-2, #ccc); border-radius: 4px;
            cursor: pointer; font-size: 13px; background: var(--canvas, #fff); }
    .step.current { background: var(--primary, #036); color: white; border-color: var(--primary, #036); }
    .step.has-blockers { border-color: var(--err, #c0392b); }
  `;

  connectedCallback() {
    super.connectedCallback();
    this._u1 = this.store?.subscribe('session', () => { this._ver = (this._ver || 0) + 1; });
    this._u2 = this.store?.subscribe('draft', () => { this._ver = (this._ver || 0) + 1; });
  }
  disconnectedCallback() { super.disconnectedCallback(); this._u1?.(); this._u2?.(); }

  _onClick(step) { navigateToStep(step); }

  render() {
    const cur = this.store?.session.currentStep ?? 'intake';
    const blockerCount = this.store?.draft.blocking?.length ?? 0;
    return html`
      <div class="bar">
        ${ALL_STEPS.map(s => html`
          <button class="step ${s === cur ? 'current' : ''} ${s === 'status' && blockerCount > 0 ? 'has-blockers' : ''}"
                  @click=${() => this._onClick(s)}>${LABELS[s]}</button>
        `)}
      </div>
    `;
  }
}

customElements.define('step-bar', StepBar);
