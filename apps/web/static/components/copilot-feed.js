import { LitElement, html, css } from 'lit';

const MAX_DISPLAY = 200;

function fmtTime(ts) {
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
}

export class CopilotFeed extends LitElement {
  static properties = { store: { attribute: false }, _ver: { state: true } };
  static styles = css`
    :host { display: block; height: 100%; }
    .panel { background: var(--muted, #f7f7f7); border: 1px solid var(--muted-2, #ddd);
             border-radius: 6px; padding: 12px; height: 100%; overflow-y: auto; font-size: 12px; }
    h4 { margin: 0 0 8px 0; color: var(--ink-2, #444); }
    .entry { padding: 6px 0; border-bottom: 1px solid var(--muted-2, #eee); }
    .ts { color: var(--ink-3, #888); margin-right: 6px; }
    .tool { font-weight: 600; }
    .empty { color: var(--ink-3, #888); }
    .truncation { padding: 8px 0; color: var(--ink-3, #888); font-style: italic; }
  `;

  connectedCallback() {
    super.connectedCallback();
    this._u = this.store?.subscribe('session', () => { this._ver = (this._ver || 0) + 1; });
  }
  disconnectedCallback() { super.disconnectedCallback(); this._u?.(); }

  render() {
    const log = this.store?.session.eventLog ?? [];
    const display = [...log].reverse().slice(0, MAX_DISPLAY);
    const truncated = log.length > MAX_DISPLAY;
    return html`
      <div class="panel">
        <h4>Co-pilot Feed</h4>
        ${display.length === 0
          ? html`<div class="empty">No events yet. Actions appear here as they happen.</div>`
          : display.map(e => html`
              <div class="entry">
                <span class="ts">${fmtTime(e.ts)}</span>
                <span class="tool">${e.tool}</span>
                · ${e.summary}
              </div>
            `)}
        ${truncated ? html`<div class="truncation">${log.length - MAX_DISPLAY} older events truncated</div>` : ''}
      </div>
    `;
  }
}

customElements.define('copilot-feed', CopilotFeed);
