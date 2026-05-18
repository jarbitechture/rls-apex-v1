import { LitElement, html, css } from 'lit';
import { navigateToStep } from '../core/router.js';

export class CurePathPanel extends LitElement {
  static properties = { store: { attribute: false }, _ver: { state: true } };
  static styles = css`
    :host { display: block; max-width: 720px; }
    .step { padding: 12px; border: 1px solid var(--muted-2, #ddd); border-radius: 6px;
            margin-bottom: 12px; }
    .title { font-weight: 600; margin-bottom: 6px; }
    .ref { display: inline-block; padding: 2px 8px; margin: 4px 4px 0 0;
           background: var(--muted, #f5f5f5); border-radius: 12px; font-size: 12px; color: var(--ink-3, #555); }
    button.mark-done { margin-top: 8px; padding: 6px 14px; opacity: 0.5; cursor: not-allowed; }
    .empty { padding: 24px; color: var(--ink-3, #777); }
    .actions { margin-top: 24px; }
    button.secondary { padding: 8px 16px; background: var(--canvas, #fff);
                       border: 1px solid var(--muted-2, #ccc); border-radius: 4px; cursor: pointer; }
  `;

  connectedCallback() {
    super.connectedCallback();
    this._u = this.store?.subscribe('draft', () => { this._ver = (this._ver || 0) + 1; });
  }
  disconnectedCallback() { super.disconnectedCallback(); this._u?.(); }

  render() {
    const steps = this.store?.draft.cureSteps ?? [];
    // GAP-1: backend ValidationResult carries no cureSteps, so an empty
    // `steps` does NOT mean "ready" — gate the ReadyForCAO message on the
    // real signal (blocking issues). cureSteps stays as the future v0.2.1
    // populated-cure-path seam.
    const blockingCount = this.store?.draft.blocking?.length ?? 0;
    return html`
      <h2>Step 4 — Cure path</h2>
      ${steps.length > 0
        ? steps.map(s => html`
            <div class="step">
              <div class="title">Step ${s.step} — ${s.title}</div>
              <div>${s.instruction}</div>
              <div>${(s.references ?? []).map(r => html`<span class="ref">${r.label}</span>`)}</div>
              <button class="mark-done" disabled
                      title="Goes live in v0.2.1 with check_attachment_metadata">Mark Done</button>
            </div>
          `)
        : blockingCount > 0
          ? html`<div class="empty">Resolve the ${blockingCount} required item${blockingCount === 1 ? '' : 's'} in Step 3 before CAO review.</div>`
          : html`<div class="empty">No cure steps — status is ReadyForCAO. Continue to Submit.</div>`}
      <div class="actions">
        <button class="secondary" @click=${() => navigateToStep('status')}>← Back to Status</button>
      </div>
    `;
  }
}

customElements.define('cure-path-panel', CurePathPanel);
