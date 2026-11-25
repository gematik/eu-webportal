/*
 * Copyright (Change Date see Readme), gematik GmbH
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *
 * ******
 *
 * For additional notes and disclaimer from gematik and in case of changes
 * by gematik, find details in the "Readme" file.
 */

import { LitElement, css, html, nothing, type PropertyValues } from 'lit';
import { countries, isIsmCountryList, type IsmCountry } from './countries';
import './ism-patient-search';
import { countryFlagEmoji, supportsFlagEmoji, type FlagDisplay } from './flag-display';
import { ismStyles } from './ism-styles';

/**
 * Kapselt Laenderauswahl und Suchmaske. `country-change` meldet die Auswahl
 * an den Host, der bei Bedarf die Browser-URL synchronisiert.
 */
export class IsmApplication extends LitElement {
  static override properties = {
    country: { type: String },
    countryOptions: { attribute: false },
    flagDisplay: { type: String, attribute: 'flag-display' },
    countriesUrl: { type: String, attribute: 'countries-url' },
    loadingCountries: { state: true },
    countryError: { state: true },
  };

  static override styles = [
    ismStyles,
    css`
      :host {
        display: block;
        max-width: var(--portal-content-width, 50rem);
        margin-inline: auto;
      }
      section {
        position: relative;
      }
      h1 {
        margin: 0;
        color: var(--ism-primary);
        font-size: 2rem;
        line-height: 1.25;
        font-weight: 750;
      }
      .subtitle {
        margin: 0.5rem 0 0;
        color: var(--ism-primary);
        font-size: 1.25rem;
      }
      .search-heading {
        display: flex;
        align-items: center;
        gap: 1rem;
        margin-top: 3.75rem;
      }
      .search-icon {
        display: grid;
        place-items: center;
        flex-shrink: 0;
        width: 2.5rem;
        height: 2.5rem;
        border-radius: 50%;
        background: var(--ism-primary);
        color: var(--ism-accent);
      }
      .search-icon svg {
        width: 1.5rem;
        height: 1.5rem;
      }
      h2 {
        margin: 0;
        color: var(--ism-primary);
        font-size: 1rem;
        font-weight: 600;
      }
      .search-heading p {
        margin: 0.25rem 0 0;
        font-size: 0.875rem;
      }
      ul {
        display: grid;
        gap: 0.25rem;
        padding: 0;
        list-style: none;
        max-height: 18rem;
        overflow: auto;
        margin: 0.25rem 0 0;
        background: var(--ism-surface);
        border: 1px solid var(--ism-border);
        border-radius: 0.25rem;
      }
      li button {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        width: 100%;
        text-align: left;
        justify-content: flex-start;
        border: 0;
        border-radius: 0;
        font-size: 1rem;
        font-weight: 400;
      }
      .country-flag {
        width: 1.25rem;
        height: 1rem;
        object-fit: contain;
        flex-shrink: 0;
      }
      .country-emoji {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 1rem;
        line-height: 1;
      }
      summary {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        min-height: 3.5rem;
        padding: 0.75rem 1rem;
        border: 1px solid var(--ism-border);
        border-radius: 0.25rem;
        background: var(--ism-surface);
        color: var(--ism-muted);
        cursor: pointer;
        list-style: none;
      }
      summary::-webkit-details-marker {
        display: none;
      }
      summary::after {
        content: '▾';
        margin-left: auto;
      }
      .country-label {
        display: block;
        margin-block: 2rem 0.5rem;
        font-size: 0.875rem;
      }
      ism-patient-search {
        margin-top: 2rem;
      }
      .back {
        margin-top: 2rem;
      }
      .back[slot] {
        margin-top: 0;
      }
      @media (max-width: 40rem) {
        section {
          padding-top: 3.5rem;
        }
        h1 {
          position: absolute;
          width: 1px;
          height: 1px;
          overflow: hidden;
          clip-path: inset(50%);
          white-space: nowrap;
        }
        .subtitle {
          display: none;
        }
        .search-heading {
          margin-top: 0;
          align-items: flex-start;
        }
        .search-heading p {
          font-size: 0.875rem;
        }
        .back {
          position: absolute;
          top: 0;
          left: 0;
          margin: 0;
          padding-left: 0;
          border-color: transparent;
          background: transparent;
        }
      }
    `,
  ];

  declare country: string;
  declare countryOptions: readonly IsmCountry[];
  declare flagDisplay: FlagDisplay;
  private readonly emojiSupport = new Map<string, boolean>();
  declare countriesUrl: string;
  declare private loadingCountries: boolean;
  declare private countryError: string;
  private countriesRequest?: AbortController;

  constructor() {
    super();
    this.country = '';
    this.countryOptions = countries;
    this.flagDisplay = 'auto';
    this.countriesUrl = '';
    this.loadingCountries = false;
    this.countryError = '';
  }

  protected override willUpdate(changed: PropertyValues): void {
    if (changed.has('countriesUrl') && this.countriesUrl) {
      void this.loadCountries();
    }
  }

  override connectedCallback(): void {
    super.connectedCallback();
    if (this.countriesUrl && this.countriesRequest?.signal.aborted) {
      void this.loadCountries();
    }
  }

  override disconnectedCallback(): void {
    this.countriesRequest?.abort();
    super.disconnectedCallback();
  }

  private async loadCountries(): Promise<void> {
    this.countriesRequest?.abort();
    const request = new AbortController();
    this.countriesRequest = request;
    this.loadingCountries = true;
    this.countryError = '';
    this.countryOptions = [];
    try {
      const response = await fetch(this.countriesUrl, { signal: request.signal });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const value: unknown = await response.json();
      if (!isIsmCountryList(value)) {
        throw new Error('Invalid country configuration');
      }
      if (!request.signal.aborted) {
        this.countryOptions = value;
      }
    } catch (error) {
      if (!request.signal.aborted) {
        console.error('ISM country configuration could not be loaded.', error);
        this.countryError = 'Die Länderkonfiguration konnte nicht geladen werden.';
      }
    } finally {
      if (!request.signal.aborted) {
        this.loadingCountries = false;
      }
    }
  }

  protected override render() {
    return html`
      <section aria-labelledby="ism-heading">
        <h1 id="ism-heading" tabindex="-1">E-Rezept-Einlösung</h1>
        <p class="subtitle">Einlösung von europäischen E-Rezepten über das Apothekenportal</p>
        <div class="search-heading">
          <span class="search-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="10" cy="10" r="6" />
              <path d="m15 15 6 6" />
            </svg>
          </span>
          <div>
            <h2>Patientensuche</h2>
            <p>
              Geben Sie die Daten des EU-Bürgers/der EU-Bürgerin ein, um auf E-Rezepte zuzugreifen.
            </p>
          </div>
        </div>
        ${
          this.countryError
            ? html`<p role="alert">${this.countryError}</p>`
            : this.loadingCountries
              ? html`<p role="status">Länderauswahl wird geladen.</p>`
              : html`${this.renderSelection()}${this.country ? this.renderSearch() : nothing}`
        }
        ${
          this.countryError ||
          this.loadingCountries ||
          !this.countryOptions.some((country) => country.code === this.country)
            ? this.renderBack()
            : nothing
        }
      </section>
    `;
  }

  private renderSelection() {
    const selected = this.countryOptions.find((country) => country.code === this.country);
    return html`
      <span class="country-label" id="country-label"
        >Zugehörigkeitsland des EU-Bürgers/der EU-Bürgerin *</span
      >
      <details @keydown=${this.onSelectionKeydown}>
        <summary aria-labelledby="country-label country-value">
          ${selected ? this.renderFlag(selected) : nothing}
          <span id="country-value">${selected?.name ?? 'Bitte Land auswählen'}</span>
        </summary>
        <ul>
          ${this.countryOptions.map(
            (country) => html`
              <li>
                <button
                  type="button"
                  data-country=${country.code}
                  @click=${() => this.selectCountry(country.code)}
                >
                  ${this.renderFlag(country)} ${country.name}
                </button>
              </li>
            `,
          )}
        </ul>
      </details>
    `;
  }

  private renderFlag(country: IsmCountry) {
    if (this.useEmoji(country.code)) {
      return html`<span class="country-flag country-emoji" aria-hidden="true"
        >${countryFlagEmoji(country.code)}</span
      >`;
    }
    return html`<img
      class="country-flag"
      src=${country.flag ?? `flags/${country.code.toLowerCase()}.svg`}
      alt=""
      width="32"
      height="24"
    />`;
  }

  private useEmoji(code: string): boolean {
    if (code.startsWith('X') || this.flagDisplay === 'svg') {
      return false;
    }
    if (this.flagDisplay === 'emoji') {
      return true;
    }
    if (!this.emojiSupport.has(code)) {
      this.emojiSupport.set(code, supportsFlagEmoji(code));
    }
    return this.emojiSupport.get(code) === true;
  }

  private renderSearch() {
    const selected = this.countryOptions.find((country) => country.code === this.country);
    return html`
      ${
        selected
          ? html`
              <ism-patient-search model-url=${`ism/${selected.code}.json`}>
                ${this.renderBack('back')}
              </ism-patient-search>
            `
          : html`<p role="alert">Für dieses Land ist keine Suchmaske verfügbar.</p>`
      }
    `;
  }

  private renderBack(slot = '') {
    return html`<button class="back" slot=${slot} type="button" @click=${this.cancelSearch}>
      ← Zurück
    </button>`;
  }

  private selectCountry(country: string): void {
    this.country = country;
    const selection = this.shadowRoot?.querySelector('details');
    if (selection) {
      selection.open = false;
      selection.querySelector('summary')?.focus();
    }
    this.dispatchEvent(
      new CustomEvent<string>('country-change', {
        detail: country,
        bubbles: true,
        composed: true,
      }),
    );
  }

  private onSelectionKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      const selection = this.shadowRoot?.querySelector('details');
      if (selection) {
        selection.open = false;
        selection.querySelector('summary')?.focus();
      }
    }
  }

  private cancelSearch(): void {
    this.dispatchEvent(new CustomEvent('search-cancel', { bubbles: true, composed: true }));
  }
}

if (!customElements.get('ism-application')) {
  customElements.define('ism-application', IsmApplication);
}
