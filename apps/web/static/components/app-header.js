import { LitElement, html, css } from 'lit';

export class AppHeader extends LitElement {
  static properties = {
    store: { attribute: false },
    surface: { attribute: false },
    _ver: { state: true },
  };

  static styles = css`
    :host { display: block; }
    .header { display: flex; align-items: center; justify-content: space-between;
              padding: 12px 16px; border-bottom: 1px solid var(--muted-2, #ddd); }
    .brand { font-weight: 600; color: var(--primary-ink, #036); }
    .right { display: flex; gap: 12px; align-items: center; }
    .upn { color: var(--ink-3, #555); font-size: 13px; }
    .banner { padding: 8px 16px; background: var(--err-bg, #fff5f5); color: var(--err, #c0392b);
              border-bottom: 1px solid var(--err, #c0392b); }
    select { padding: 4px 8px; border: 1px solid var(--muted-2, #ccc); border-radius: 4px; }
  `;

  connectedCallback() {
    super.connectedCallback();
    this._unsub = this.store?.subscribe('session', () => { this._ver = (this._ver || 0) + 1; });
  }
  disconnectedCallback() { super.disconnectedCallback(); this._unsub?.(); }

  _onRoleChange(e) {
    this.store.update('session', s => { s.role = e.target.value; });
  }

  render() {
    const role = this.store?.session.role ?? 'requester';
    const upn = this.store?.session.upn ?? '—';
    const banners = this.surface?.banners ?? [];
    return html`
      ${banners.map(b => html`<div class="banner">${b.kind === 'breaker-open'
        ? `Breaker open for ${b.name} — events queue locally until recovery.`
        : `Validator ${b.tool} unavailable — partial validation only.`}</div>`)}
      <div class="header">
        <span class="brand">RLS Apex · Manatee County</span>
        <div class="right">
          <span class="upn">${upn}</span>
          <select aria-label="role" .value=${role} @change=${this._onRoleChange}>
            <option value="requester">Requester</option>
            <option value="cao">CAO Reviewer</option>
          </select>
        </div>
      </div>
    `;
  }
}

customElements.define('app-header', AppHeader);
