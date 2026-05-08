import { LitElement, html, css } from 'lit';
import { navigateToStep } from '../core/router.js';

export class SubmitPanel extends LitElement {
  static properties = { store: { attribute: false }, _ver: { state: true } };
  static styles = css`
    :host { display: block; max-width: 720px; }
    .summary { background: var(--muted, #f5f5f5); padding: 12px; border-radius: 4px; margin: 16px 0; }
    pre { background: var(--canvas, #fff); padding: 12px; border: 1px solid var(--muted-2, #ddd);
          border-radius: 4px; overflow-x: auto; cursor: copy; font-size: 12px; }
    pre.copied::after { content: ' ✓ Copied'; color: var(--success, #2e7d32); }
    button.submit { padding: 10px 20px; background: var(--primary, #036); color: white;
                    border: none; border-radius: 4px; opacity: 0.5; cursor: not-allowed; }
    .note { margin-top: 16px; color: var(--ink-3, #555); font-size: 13px; }
  `;

  connectedCallback() {
    super.connectedCallback();
    this._u = this.store?.subscribe('draft', () => { this._ver = (this._ver || 0) + 1; });
  }
  disconnectedCallback() { super.disconnectedCallback(); this._u?.(); }

  async _copy(e) {
    const text = e.currentTarget.textContent;
    await navigator.clipboard?.writeText(text);
    e.currentTarget.classList.add('copied');
    setTimeout(() => e.currentTarget.classList.remove('copied'), 1500);
  }

  render() {
    const payload = this.store?.draft.rlsPayload ?? {};
    return html`
      <h2>Step 5 — Review and submit</h2>
      <div class="summary">
        <strong>${payload.title || '(no title)'}</strong><br>
        Department: ${payload.department || '—'}
      </div>
      <button class="submit" disabled
              title="Submit goes live in v0.2.1 with update_rls_status. Pilot escape hatch: copy the JSON below and email to County Attorney.">
        Submit
      </button>
      <p class="note">
        Submit goes live in v0.2.1 with the <code>update_rls_status</code> tool. For the pilot,
        click the JSON below to copy and email it to the County Attorney's office.
      </p>
      <pre @click=${this._copy}>${JSON.stringify(payload, null, 2)}</pre>
      <button @click=${() => navigateToStep('cure')}>← Back to Cure path</button>
    `;
  }
}

customElements.define('submit-panel', SubmitPanel);
