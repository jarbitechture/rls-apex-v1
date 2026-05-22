import { LitElement, html, css } from 'lit';
import { navigateToStep } from '../core/router.js';
import { postSubmit } from '../core/api.js';

export class SubmitPanel extends LitElement {
  static properties = { store: { attribute: false }, _ver: { state: true } };
  static styles = css`
    :host { display: block; max-width: 720px; }
    .summary { background: var(--muted, #f5f5f5); padding: 12px; border-radius: 4px; margin: 16px 0; }
    pre { background: var(--canvas, #fff); padding: 12px; border: 1px solid var(--muted-2, #ddd);
          border-radius: 4px; overflow-x: auto; cursor: copy; font-size: 12px; }
    pre.copied::after { content: ' ✓ Copied'; color: var(--success, #2e7d32); }
    button.submit { padding: 10px 20px; background: var(--primary, #036); color: white;
                    border: none; border-radius: 4px; cursor: pointer; }
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

  async _digest(obj) {
    const sorted = {};
    for (const k of Object.keys(obj).sort()) sorted[k] = String(obj[k] ?? '');
    sorted.chain_version = '1';
    const json = JSON.stringify(sorted);
    const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(json));
    return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, '0')).join('');
  }

  async _submit() {
    const payload = this.store?.draft.rlsPayload ?? {};
    const idempotency_key = await this._digest(payload);
    const res = await postSubmit({ rlsPayload: payload, idempotency_key });
    this.store.update('draft', d => { d.rlsId = res.rls_id; });
    this._submitted = res;
    this.requestUpdate();
  }

  render() {
    const payload = this.store?.draft.rlsPayload ?? {};
    return html`
      <h2>Step 5 — Review and submit</h2>
      <div class="summary">
        <strong>${payload.title || '(no title)'}</strong><br>
        Department: ${payload.department || '—'}
      </div>
      <button class="submit" @click=${() => this._submit()}>Submit</button>
      <p class="note">
        Submit persists the RLS and returns a lineage receipt. The JSON below
        stays copyable as a record.
      </p>
      <pre @click=${this._copy}>${JSON.stringify(payload, null, 2)}</pre>
      <button @click=${() => navigateToStep('cure')}>← Back to Cure path</button>
    `;
  }
}

customElements.define('submit-panel', SubmitPanel);
