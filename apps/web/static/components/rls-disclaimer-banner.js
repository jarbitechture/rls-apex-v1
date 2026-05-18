// COMPLIANCE: This banner must be present on every user-facing surface of rls-apex-v1.
// Lock #19 (validator framing) and TAC-02 (legal disclaimer) both depend on its visibility.
// If migrating to any future frontend, you MUST port this component first and keep
// tests/e2e/disclaimer.spec.js asserting [data-testid="rls-disclaimer-banner"] in the new
// layer's rendered DOM. The Playwright assertion is the load-bearing guard — do not weaken it
// to a text-match or remove the testid.

import { LitElement, html, css } from 'lit';

const DISCLAIMER_TEXT =
  'Grades a request-for-legal-services draft against procedure and precedent. ' +
  'Does not provide legal advice. Does not cite case law.';

export class RlsDisclaimerBanner extends LitElement {
  static styles = css`
    :host {
      display: block;
    }
    /* WCAG AA contrast: #1f2937 ink on #fef3c7 amber background.
       Measured contrast ratio: ~10.2:1 (exceeds 4.5:1 AA for normal text). */
    .banner {
      padding: 10px 16px;
      background: #fef3c7;
      color: #1f2937;
      border-bottom: 1px solid #d4a72c;
      font-size: 13px;
      line-height: 1.4;
    }
    .label {
      font-weight: 600;
      margin-right: 6px;
    }
  `;

  connectedCallback() {
    super.connectedCallback();
    // Host attribute (light DOM) so Playwright can query [data-testid="..."]
    // without shadow-DOM piercing.
    this.setAttribute('data-testid', 'rls-disclaimer-banner');
    if (!this.hasAttribute('role')) this.setAttribute('role', 'note');
    if (!this.hasAttribute('aria-label')) this.setAttribute('aria-label', 'Legal disclaimer');
  }

  render() {
    return html`
      <div class="banner">
        <span class="label">Notice:</span><span>${DISCLAIMER_TEXT}</span>
      </div>
    `;
  }
}

customElements.define('rls-disclaimer-banner', RlsDisclaimerBanner);
