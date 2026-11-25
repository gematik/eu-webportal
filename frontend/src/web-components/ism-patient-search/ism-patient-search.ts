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

import { LitElement, css, html, nothing } from 'lit';
import {
  FieldError,
  IsmField,
  IsmChoiceGroup,
  IsmHelpMedia,
  IsmPatientSearchModel,
  isIsmPatientSearchModel,
  generationErrorMessage,
  validateField,
} from './ism-model';
import { ismStyles } from './ism-styles';

const ERROR_TEXT: Record<FieldError, string> = {
  required: 'Dieses Feld ist ein Pflichtfeld.',
  pattern: 'Die Eingabe entspricht nicht dem erwarteten Format.',
};

/**
 * Zeigt die Patientensuche eines Landes aus dem beim Build erzeugten Modell an.
 * Die Eingaben werden geprüft, aber nicht abgesendet.
 *
 * @attr model-url URL der Modelldatei, z. B. `ism/PL.json`.
 * @slot back Navigation links in der gemeinsamen Aktionszeile.
 */
export class IsmPatientSearch extends LitElement {
  static override properties = {
    modelUrl: { attribute: 'model-url' },
    model: { state: true },
    loadError: { state: true },
    values: { state: true },
    touched: { state: true },
    selections: { state: true },
    privacyConfirmed: { state: true },
    helpOpen: { state: true },
    submitted: { state: true },
  };

  static override styles = [
    ismStyles,
    css`
      :host {
        display: block;
      }
      form {
        display: grid;
        gap: 2rem;
      }
      label {
        display: block;
        font-size: 0.875rem;
        font-weight: 400;
      }
      .field-label {
        position: relative;
        display: flex;
        align-items: flex-start;
        gap: 0.5rem;
      }
      .field-label label {
        min-width: 0;
        overflow-wrap: anywhere;
      }
      .field-info {
        flex-shrink: 0;
      }
      .field-info summary {
        display: grid;
        place-items: center;
        min-width: 1.5rem;
        min-height: 1.5rem;
        color: var(--ism-primary);
        cursor: pointer;
        list-style: none;
      }
      .field-info summary::-webkit-details-marker {
        display: none;
      }
      .field-info .hint {
        position: absolute;
        z-index: 1;
        top: 100%;
        left: 0;
        width: min(20rem, 100%);
        padding: 0.75rem;
        border: 1px solid var(--ism-border);
        border-radius: 0.25rem;
        background: var(--ism-surface);
        box-shadow: 0 0.25rem 0.75rem rgb(0 0 0 / 12%);
      }
      fieldset {
        min-width: 0;
        margin: 0;
        padding: 1rem;
        border: 1px solid var(--ism-border);
        border-radius: 0.25rem;
      }
      fieldset > div {
        margin-top: 1.5rem;
      }
      legend {
        color: var(--ism-primary);
        font-weight: 600;
      }
      .original,
      .hint {
        display: block;
        color: var(--ism-muted);
        font-size: 0.875rem;
        font-weight: 400;
        overflow-wrap: anywhere;
      }
      .required {
        color: var(--ism-text);
      }
      input,
      select {
        width: 100%;
        min-height: 3.5rem;
        margin-top: 0.5rem;
        padding: 0.75rem 1rem;
        border: 1px solid var(--ism-border);
        border-radius: 0.25rem;
        font: inherit;
        background: var(--ism-surface);
        color: var(--ism-text);
      }
      input[aria-invalid='true'] {
        border-color: var(--ism-error);
      }
      .error {
        margin: 0.25rem 0 0;
        color: var(--ism-error);
        font-size: 0.875rem;
      }
      .error:empty {
        display: none;
      }
      figure {
        max-width: 32rem;
        margin: 1.5rem 0 0;
      }
      img {
        max-width: 100%;
        height: auto;
        border: 1px solid var(--ism-border);
        border-radius: 0.25rem;
      }
      .privacy {
        display: flex;
        align-items: flex-start;
        gap: 0.5rem;
        font-weight: 400;
      }
      .privacy input {
        width: auto;
        flex-shrink: 0;
        margin-top: 0.35rem;
        min-height: auto;
        accent-color: var(--ism-primary);
      }
      button[type='submit'] {
        background: var(--ism-primary);
        color: var(--ism-accent);
      }
      button[type='submit']:hover:not(:disabled) {
        background: var(--ism-primary);
        box-shadow: 0 0 0 0.125rem var(--ism-primary);
      }
      button:disabled {
        border-color: var(--ism-disabled);
        background: var(--ism-disabled);
        color: var(--ism-primary);
        cursor: not-allowed;
      }
      .actions {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        justify-content: flex-end;
        gap: 0.5rem;
      }
      .back-action {
        display: flex;
        margin-inline-end: auto;
      }
      .help-toggle {
        justify-self: start;
        min-height: 2.75rem;
        padding: 0;
        border: 0;
        border-radius: 0;
        color: var(--ism-link);
        text-decoration: underline;
        text-underline-offset: 0.2em;
        font-weight: 400;
      }
      .help-toggle span {
        text-decoration: none;
        font-size: 1.25rem;
      }
      @media (max-width: 40rem) {
        .actions {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .back-action {
          display: contents;
        }
        .actions button {
          width: 100%;
          padding-inline: 0.5rem;
        }
      }
    `,
  ];

  declare modelUrl: string | null;
  declare model: IsmPatientSearchModel | null;
  declare loadError: string | null;
  declare values: Readonly<Record<number, string>>;
  declare touched: ReadonlySet<number>;
  declare selections: Readonly<Record<number, number>>;
  declare privacyConfirmed: boolean;
  declare helpOpen: boolean;
  declare private submitted: boolean;
  private loadRequest = 0;

  constructor() {
    super();
    this.modelUrl = null;
    this.model = null;
    this.loadError = null;
    this.values = {};
    this.touched = new Set();
    this.selections = {};
    this.privacyConfirmed = false;
    this.helpOpen = false;
    this.submitted = false;
  }

  protected override willUpdate(changed: Map<PropertyKey, unknown>): void {
    if (changed.has('modelUrl')) {
      void this.load();
    }
  }

  private async load(): Promise<void> {
    const request = ++this.loadRequest;
    this.model = null;
    this.loadError = null;
    this.values = {};
    this.touched = new Set();
    this.selections = {};
    this.privacyConfirmed = false;
    this.helpOpen = false;
    this.submitted = false;
    if (!this.modelUrl) {
      this.loadError = 'keine Modell-URL angegeben';
      return;
    }
    try {
      const response = await fetch(this.modelUrl);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const model: unknown = await response.json();
      const generationError = generationErrorMessage(model);
      if (generationError !== null) {
        throw new Error(generationError);
      }
      if (!isIsmPatientSearchModel(model)) {
        throw new Error('unbekanntes Modellformat');
      }
      if (request === this.loadRequest) {
        this.model = model;
      }
    } catch (error) {
      if (request === this.loadRequest) {
        this.loadError = error instanceof Error ? error.message : String(error);
      }
    }
  }

  protected override render() {
    if (this.loadError !== null) {
      return html`<p role="alert">Die Suchmaske konnte nicht geladen werden (${this.loadError}).</p>
        <slot name="back"></slot>`;
    }
    if (this.model === null) {
      return html`<p role="status">Suchmaske wird geladen …</p>
        <slot name="back"></slot>`;
    }
    const { fields, helpMedia, choiceGroups = [] } = this.model.patientSearch;
    return html`
      <form novalidate @submit=${this.onSubmit}>
        ${fields.map((field, index) => {
          const groupIndex = choiceGroups.findIndex((group) =>
            group.alternatives.some((alternative) => alternative.fieldIndexes.includes(index)),
          );
          if (groupIndex < 0) {
            return this.renderField(field, index);
          }
          const group = choiceGroups[groupIndex];
          return index === group.alternatives[0].fieldIndexes[0]
            ? this.renderChoice(group, groupIndex, fields)
            : nothing;
        })}
        ${
          helpMedia.length
            ? html`
                <button
                  class="help-toggle"
                  type="button"
                  aria-controls="search-help"
                  aria-expanded=${this.helpOpen}
                  @click=${() => (this.helpOpen = !this.helpOpen)}
                >
                  <span aria-hidden="true">ⓘ</span> Hilfe zur Patientensuche
                </button>
                ${
                  this.helpOpen
                    ? html`<section id="search-help" aria-label="Hilfe zur Patientensuche">
                        ${helpMedia.map((media) => this.renderMedia(media))}
                      </section>`
                    : html`<section id="search-help" hidden></section>`
                }
              `
            : nothing
        }
        <label class="privacy">
          <input
            type="checkbox"
            required
            .checked=${this.privacyConfirmed}
            @change=${(event: Event) => {
              this.privacyConfirmed = (event.target as HTMLInputElement).checked;
              this.submitted = false;
            }}
          />
          <span
            >Ich bestätige, dass ich der EU-Bürgerin/dem EU-Bürger die Information über die
            Datenschutzbestimmungen im Rahmen der grenzüberschreitenden Behandlung zur Verfügung
            gestellt habe.</span
          >
        </label>
        <div class="actions">
          <div class="back-action"><slot name="back"></slot></div>
          <button type="button" @click=${this.cancelSearch}>Abbrechen</button>
          <button type="submit" ?disabled=${!this.canSearch()}>
            <span aria-hidden="true">→</span> Patient suchen
          </button>
        </div>
        ${
          this.submitted
            ? html`<p role="status">
                Die Eingaben sind gültig. Dieser Demonstrator sendet keine Suchanfrage ab.
              </p>`
            : nothing
        }
      </form>
    `;
  }

  private renderChoice(group: IsmChoiceGroup, groupIndex: number, fields: readonly IsmField[]) {
    const selected = this.selections[groupIndex];
    const alternative = selected === undefined ? undefined : group.alternatives[selected];
    const id = `choice-${groupIndex}`;
    return html`
      <fieldset>
        <legend>Suchverfahren ${groupIndex + 1}</legend>
        <label for=${id}>Bitte wählen Sie ein Suchverfahren aus.</label>
        <select
          id=${id}
          required
          .value=${selected === undefined ? '' : String(selected)}
          @change=${(event: Event) => {
            const value = (event.target as HTMLSelectElement).value;
            this.selections = { ...this.selections, [groupIndex]: Number(value) };
            this.submitted = false;
          }}
        >
          <option value="" disabled>Bitte auswählen</option>
          ${group.alternatives.map(
            (option, index) => html`<option value=${index}>${option.display}</option>`,
          )}
        </select>
        ${
          alternative
            ? alternative.fieldIndexes.map((index) => this.renderField(fields[index], index))
            : nothing
        }
      </fieldset>
    `;
  }

  private renderField(field: IsmField, index: number) {
    const id = `field-${index}`;
    const value = this.values[index] ?? '';
    const error = this.touched.has(index) ? validateField(field, value) : null;
    return html`
      <div>
        <div class="field-label">
          <label for=${id}>
            ${field.description}
            ${field.mandatory ? html`<span class="required" aria-hidden="true">*</span>` : nothing}
            ${
              field.originalDescription
                ? html`<span class="original">${field.originalDescription}</span>`
                : nothing
            }
          </label>
          <details class="field-info" @keydown=${this.onFieldInfoKeydown}>
            <summary aria-label=${`Formatinformationen zu ${field.description}`}>
              <span aria-hidden="true">ⓘ</span>
            </summary>
            <span class="hint" id="${id}-hint">
              ${
                field.pattern
                  ? `Erwartetes Format: ${field.pattern}`
                  : 'Für dieses Feld ist kein Format vorgegeben.'
              }
            </span>
          </details>
        </div>
        <input
          id=${id}
          name=${field.label}
          type="text"
          autocomplete="off"
          ?required=${field.mandatory}
          aria-invalid=${error ? 'true' : 'false'}
          aria-describedby="${id}-hint ${id}-error"
          .value=${value}
          @input=${(event: Event) => this.onInput(index, event)}
          @blur=${() => this.markTouched(index)}
        />
        <p class="error" id="${id}-error" role="alert">${error ? ERROR_TEXT[error] : nothing}</p>
      </div>
    `;
  }

  private renderMedia(media: IsmHelpMedia) {
    const source = new URL(media.file, new URL(this.modelUrl ?? '', document.baseURI));
    return html`
      <figure>
        <img src=${source.href} alt=${media.description ?? media.name} />
        ${media.description ? html`<figcaption>${media.description}</figcaption>` : nothing}
      </figure>
    `;
  }

  private onFieldInfoKeydown(event: KeyboardEvent): void {
    if (event.key !== 'Escape' || !(event.currentTarget instanceof HTMLDetailsElement)) {
      return;
    }
    event.currentTarget.open = false;
    event.currentTarget.querySelector('summary')?.focus();
  }

  private markTouched(index: number): void {
    this.touched = new Set(this.touched).add(index);
  }

  private onInput(index: number, event: Event): void {
    this.values = { ...this.values, [index]: (event.target as HTMLInputElement).value };
    this.submitted = false;
    this.markTouched(index);
  }

  private canSearch(): boolean {
    if (!this.model || !this.privacyConfirmed) {
      return false;
    }
    const { fields, choiceGroups = [] } = this.model.patientSearch;
    if (choiceGroups.some((group, index) => !group.alternatives[this.selections[index]])) {
      return false;
    }
    return fields.every((field, index) => {
      const groupIndex = choiceGroups.findIndex((group) =>
        group.alternatives.some((alternative) => alternative.fieldIndexes.includes(index)),
      );
      const active =
        groupIndex < 0 ||
        choiceGroups[groupIndex].alternatives[this.selections[groupIndex]].fieldIndexes.includes(
          index,
        );
      return !active || validateField(field, this.values[index] ?? '') === null;
    });
  }

  private onSubmit(event: Event): void {
    event.preventDefault();
    this.submitted = this.canSearch();
  }

  private cancelSearch(): void {
    this.dispatchEvent(new CustomEvent('search-cancel', { bubbles: true, composed: true }));
  }
}

if (!customElements.get('ism-patient-search')) {
  customElements.define('ism-patient-search', IsmPatientSearch);
}
