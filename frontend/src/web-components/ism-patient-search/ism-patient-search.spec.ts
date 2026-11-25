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

import './ism-patient-search';
import type { IsmPatientSearch } from './ism-patient-search';
import { IsmPatientSearchModel } from './ism-model';

const model: IsmPatientSearchModel = {
  modelVersion: 1,
  country: { code: 'XA', label: 'label.ism.addressCountry' },
  patientSearch: {
    friendlyName: null,
    scope: 'ALL',
    fields: [
      {
        domain: '1.2.3',
        label: 'label.ism.id',
        description: 'Example identifier',
        originalDescription: 'Synthetic identifier',
        mandatory: true,
        pattern: '^[A-Z]{2}$',
      },
      {
        domain: '4.5.6',
        label: 'label.ism.other',
        description: 'Other',
        originalDescription: null,
        mandatory: false,
        pattern: null,
      },
    ],
    helpMedia: [
      { description: 'Example card', file: 'XA-card.jpg', mediaType: 'image/jpeg', name: 'card' },
    ],
  },
};

function respondWith(response: Partial<Response>): void {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response));
}

async function create(modelUrl = 'ism/XA.json'): Promise<IsmPatientSearch> {
  expect(customElements.get('ism-patient-search')).toBeDefined();
  const element = document.createElement('ism-patient-search') as IsmPatientSearch;
  element.setAttribute('model-url', modelUrl);
  document.body.append(element);
  await vi.waitFor(() => expect(element.model != null || element.loadError != null).toBe(true));
  await element.updateComplete;
  return element;
}

function input(element: IsmPatientSearch, index = 0): HTMLInputElement {
  return element.shadowRoot!.querySelectorAll<HTMLInputElement>('input[type="text"]')[index];
}

async function type(element: IsmPatientSearch, value: string, index = 0): Promise<void> {
  const field = input(element, index);
  field.value = value;
  field.dispatchEvent(new Event('input'));
  await element.updateComplete;
}

const errorText = (element: IsmPatientSearch, index = 0) =>
  element.shadowRoot!.querySelectorAll('.error')[index].textContent?.trim();

describe('IsmPatientSearch', () => {
  beforeEach(() => respondWith({ ok: true, json: async () => model }));

  afterEach(() => {
    document.body.replaceChildren();
    vi.unstubAllGlobals();
  });

  it('should render every search field with descriptions, mandatory marker and format', async () => {
    const element = await create();
    const root = element.shadowRoot!;

    expect(root.querySelectorAll('input[type="text"]')).toHaveLength(2);
    expect(root.querySelector('label')?.textContent).toContain('Example identifier');
    expect(root.querySelector('label')?.textContent).toContain('Synthetic identifier');
    expect(input(element).required).toBe(true);
    expect(root.querySelector('.hint')?.textContent).toContain('^[A-Z]{2}$');
    expect(root.querySelectorAll('.hint')[1].textContent).toContain('kein Format');
    expect(fetch).toHaveBeenCalledWith('ism/XA.json');
  });

  it('should show help media resolved relative to the model', async () => {
    const element = await create('ism/XA.json');
    expect(element.shadowRoot!.querySelector('img')).toBeNull();
    const toggle = element.shadowRoot!.querySelector<HTMLButtonElement>('.help-toggle')!;
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    toggle.click();
    await element.updateComplete;
    const image = element.shadowRoot!.querySelector('img')!;

    expect(new URL(image.src).pathname.endsWith('/ism/XA-card.jpg')).toBe(true);
    expect(image.alt).toBe('Example card');
    expect(toggle.getAttribute('aria-expanded')).toBe('true');
    toggle.click();
    await element.updateComplete;
    expect(element.shadowRoot!.querySelector('img')).toBeNull();
  });

  it('should expose format information through a keyboard accessible information toggle', async () => {
    const element = await create();
    const details = element.shadowRoot!.querySelector<HTMLDetailsElement>('.field-info')!;
    const toggle = details.querySelector('summary')!;
    expect(details.open).toBe(false);
    expect(toggle.getAttribute('aria-label')).toBe('Formatinformationen zu Example identifier');
    expect(details.querySelector('.hint')?.id).toBe('field-0-hint');
    toggle.click();
    expect(details.open).toBe(true);
    expect(details.textContent).toContain('^[A-Z]{2}$');
    details.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(details.open).toBe(false);
    expect(element.shadowRoot!.activeElement).toBe(toggle);
    expect(input(element).value).toBe('');
  });

  it('should omit the information button when no help images exist', async () => {
    respondWith({
      ok: true,
      json: async () => ({ ...model, patientSearch: { ...model.patientSearch, helpMedia: [] } }),
    });
    const element = await create();
    expect(element.shadowRoot!.querySelector('.help-toggle')).toBeNull();
  });

  it('should require valid fields and privacy confirmation before searching', async () => {
    const element = await create();
    const root = element.shadowRoot!;
    const submit = root.querySelector<HTMLButtonElement>('button[type="submit"]')!;
    const privacy = root.querySelector<HTMLInputElement>('input[type="checkbox"]')!;
    expect(submit.disabled).toBe(true);
    privacy.checked = true;
    privacy.dispatchEvent(new Event('change'));
    await element.updateComplete;
    expect(submit.disabled).toBe(true);
    await type(element, 'AB');
    expect(submit.disabled).toBe(false);
    submit.click();
    await element.updateComplete;
    expect(root.querySelector('[role="status"]')?.textContent).toContain('keine Suchanfrage');
    privacy.checked = false;
    privacy.dispatchEvent(new Event('change'));
    await element.updateComplete;
    expect(submit.disabled).toBe(true);
    expect(root.querySelector('[role="status"]')).toBeNull();
    root.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));
    await element.updateComplete;
    expect(root.querySelector('[role="status"]')).toBeNull();
  });

  it('should emit cancellation without submitting patient data', async () => {
    const element = await create();
    const cancelled = vi.fn();
    element.addEventListener('search-cancel', cancelled);
    element.shadowRoot!.querySelector<HTMLButtonElement>('.actions button[type="button"]')!.click();
    expect(cancelled).toHaveBeenCalledOnce();
    expect(cancelled.mock.calls[0][0].composed).toBe(true);
  });

  it('should render back navigation alongside cancel and search actions', async () => {
    const element = await create();
    const back = document.createElement('button');
    back.slot = 'back';
    back.textContent = 'Zurück';
    element.append(back);
    await element.updateComplete;
    const actions = element.shadowRoot!.querySelector('.actions')!;
    const slot = actions.querySelector<HTMLSlotElement>('slot[name="back"]')!;
    expect(slot.assignedElements()).toEqual([back]);
    expect(actions.querySelector('button[type="button"]')?.textContent).toBe('Abbrechen');
    expect(actions.querySelector('button[type="submit"]')).not.toBeNull();
  });

  it.each(['loading', 'error'])(
    'should keep back navigation available during %s',
    async (state) => {
      const element = await create();
      element.model = null;
      element.loadError = state === 'error' ? 'HTTP 404' : null;
      await element.updateComplete;
      expect(element.shadowRoot!.querySelector('slot[name="back"]')).not.toBeNull();
    },
  );

  it('should validate the format while typing', async () => {
    const element = await create();

    expect(errorText(element)).toBe('');
    await type(element, '123');
    expect(errorText(element)).toBe('Die Eingabe entspricht nicht dem erwarteten Format.');
    expect(input(element).getAttribute('aria-invalid')).toBe('true');

    await type(element, 'AB');
    expect(errorText(element)).toBe('');
    expect(input(element).getAttribute('aria-invalid')).toBe('false');
  });

  it('should report an emptied mandatory field and ignore a field without pattern', async () => {
    const element = await create();

    await type(element, '1');
    await type(element, '');
    await type(element, 'free text', 1);

    expect(errorText(element)).toBe('Dieses Feld ist ein Pflichtfeld.');
    expect(errorText(element, 1)).toBe('');
  });

  it.each([
    {
      country: 'XA',
      descriptions: ['Example identifier', 'Example number'],
      patterns: ['^[A-Z]{3}$', '^\\d{2}$'],
      valid: ['ABC', '12'],
    },
    {
      country: 'XB',
      descriptions: ['Synthetic code', 'Synthetic suffix'],
      patterns: ['^[A-Z]{2}$', '^[0-9]{2}$'],
      valid: ['AB', '12'],
    },
    {
      country: 'XC',
      descriptions: ['Example token', 'Example serial'],
      patterns: ['^[A-Z]{3}$', '^[0-9]{3}$'],
      valid: ['ABC', '123'],
    },
  ])('should independently validate both fields using $country rules', async (reference) => {
    respondWith({
      ok: true,
      json: async () => ({
        ...model,
        country: { ...model.country, code: reference.country },
        patientSearch: {
          ...model.patientSearch,
          fields: model.patientSearch.fields.map((field, index) => ({
            ...field,
            description: reference.descriptions[index],
            pattern: reference.patterns[index],
            mandatory: true,
          })),
        },
      }),
    });
    const element = await create(`ism/${reference.country}.json`);
    const labels = element.shadowRoot!.querySelectorAll('label');
    expect(labels).toHaveLength(3);
    reference.descriptions.forEach((description, index) =>
      expect(labels[index].textContent).toContain(description),
    );

    await type(element, 'invalid');
    expect(errorText(element)).toContain('erwarteten Format');
    expect(errorText(element, 1)).toBe('');
    await type(element, reference.valid[1], 1);
    expect(input(element).value).toBe('invalid');
    expect(errorText(element)).toContain('erwarteten Format');
    expect(errorText(element, 1)).toBe('');
    await type(element, reference.valid[0]);
    expect(errorText(element)).toBe('');
    await type(element, '', 1);
    expect(errorText(element, 1)).toContain('Pflichtfeld');
    expect(input(element).value).toBe(reference.valid[0]);
    expect(errorText(element)).toBe('');
  });

  it('should keep values, touch state and accessible IDs separate for identical domains and labels', async () => {
    respondWith({
      ok: true,
      json: async () => ({
        ...model,
        patientSearch: {
          ...model.patientSearch,
          fields: [
            model.patientSearch.fields[0],
            { ...model.patientSearch.fields[0], mandatory: false, pattern: null },
          ],
        },
      }),
    });
    const element = await create();
    expect(input(element).id).not.toBe(input(element, 1).id);
    for (const field of element.shadowRoot!.querySelectorAll('input[type="text"]')) {
      expect(element.shadowRoot!.querySelector(`label[for="${field.id}"]`)).not.toBeNull();
      for (const id of field.getAttribute('aria-describedby')!.split(' ')) {
        expect(element.shadowRoot!.getElementById(id)).not.toBeNull();
      }
    }
    input(element).dispatchEvent(new Event('blur'));
    await element.updateComplete;
    expect(errorText(element)).toContain('Pflichtfeld');
    expect(errorText(element, 1)).toBe('');
    await type(element, 'free text', 1);
    expect(input(element).value).toBe('');
    expect(errorText(element)).toContain('Pflichtfeld');
    expect(errorText(element, 1)).toBe('');
    await type(element, 'AB');
    expect(input(element, 1).value).toBe('free text');
    expect(errorText(element)).toBe('');
  });

  it('should reset every field value and touched state when loading another mask', async () => {
    const element = await create();
    await type(element, 'invalid');
    await type(element, 'other', 1);
    element.privacyConfirmed = true;
    element.helpOpen = true;
    const nextModel = { ...model, country: { ...model.country, code: 'XB' } };
    respondWith({ ok: true, json: async () => nextModel });
    element.setAttribute('model-url', 'ism/XB.json');
    await vi.waitFor(() => expect(element.model?.country.code).toBe('XB'));
    await element.updateComplete;
    expect(input(element).value).toBe('');
    expect(input(element, 1).value).toBe('');
    expect(errorText(element)).toBe('');
    expect(errorText(element, 1)).toBe('');
    expect(element.privacyConfirmed).toBe(false);
    expect(element.helpOpen).toBe(false);
    expect(
      element.shadowRoot!.querySelector<HTMLInputElement>('input[type="checkbox"]')!.checked,
    ).toBe(false);
  });

  it('should not submit the form', async () => {
    const element = await create();
    const event = new Event('submit', { cancelable: true });

    element.shadowRoot!.querySelector('form')!.dispatchEvent(event);

    expect(event.defaultPrevented).toBe(true);
  });

  it('should require deliberate CHOICE selection and preserve values and errors per alternative', async () => {
    respondWith({
      ok: true,
      json: async () => ({
        ...model,
        patientSearch: {
          ...model.patientSearch,
          fields: [
            model.patientSearch.fields[0],
            { ...model.patientSearch.fields[0], description: 'Second', pattern: '[A-Z]+' },
          ],
          choiceGroups: [
            {
              alternatives: [
                { display: 'Regional', fieldIndexes: [0] },
                { display: 'National', fieldIndexes: [1] },
              ],
            },
          ],
        },
      }),
    });
    const element = await create();
    element.privacyConfirmed = true;
    await element.updateComplete;
    const submit = element.shadowRoot!.querySelector<HTMLButtonElement>('button[type="submit"]')!;
    const select = element.shadowRoot!.querySelector('select')!;
    const choose = async (value: string) => {
      select.value = value;
      select.dispatchEvent(new Event('change'));
      await element.updateComplete;
    };
    expect(select.value).toBe('');
    expect(select.required).toBe(true);
    expect(submit.disabled).toBe(true);
    expect(element.shadowRoot!.querySelectorAll('input[type="text"]')).toHaveLength(0);
    await choose('0');
    await type(element, 'invalid');
    expect(errorText(element)).toContain('erwarteten Format');
    expect(submit.disabled).toBe(true);
    await choose('1');
    expect(input(element).value).toBe('');
    expect(errorText(element)).toBe('');
    await type(element, 'ABC');
    expect(errorText(element)).toBe('');
    expect(submit.disabled).toBe(false);
    await choose('0');
    expect(input(element).value).toBe('invalid');
    expect(errorText(element)).toContain('erwarteten Format');
    expect(submit.disabled).toBe(true);
    await choose('1');
    expect(input(element).value).toBe('ABC');
    expect(errorText(element)).toBe('');
    expect(submit.disabled).toBe(false);
    element.setAttribute('model-url', 'ism/XC.json');
    await element.updateComplete;
    await vi.waitFor(() => expect(element.shadowRoot!.querySelector('select')?.value).toBe(''));
    expect(element.shadowRoot!.querySelectorAll('input[type="text"]')).toHaveLength(0);
  });

  it('should select multiple CHOICE groups independently alongside NORMAL fields', async () => {
    respondWith({
      ok: true,
      json: async () => ({
        ...model,
        patientSearch: {
          ...model.patientSearch,
          fields: Array.from({ length: 3 }, () => model.patientSearch.fields[0]),
          choiceGroups: [
            { alternatives: [{ display: 'First', fieldIndexes: [0] }] },
            { alternatives: [{ display: 'Second', fieldIndexes: [2] }] },
          ],
        },
      }),
    });
    const element = await create();
    expect(element.shadowRoot!.querySelectorAll('input[type="text"]')).toHaveLength(1);
    const selects = element.shadowRoot!.querySelectorAll('select');
    selects[0].value = '0';
    selects[0].dispatchEvent(new Event('change'));
    await element.updateComplete;
    expect(selects[1].value).toBe('');
    expect(element.shadowRoot!.querySelectorAll('input[type="text"]')).toHaveLength(2);
    await type(element, '123');
    selects[1].value = '0';
    selects[1].dispatchEvent(new Event('change'));
    await element.updateComplete;
    expect(element.shadowRoot!.querySelectorAll('input[type="text"]')).toHaveLength(3);
    expect(input(element).value).toBe('123');
    expect(errorText(element, 2)).toBe('');
  });

  it('should show an error when the model cannot be loaded', async () => {
    respondWith({ ok: false, status: 404 });
    const element = await create();

    expect(element.shadowRoot!.querySelector('[role="alert"]')?.textContent).toContain('HTTP 404');
    expect(element.shadowRoot!.querySelector('form')).toBeNull();
  });

  it('should reject a model with an unknown format', async () => {
    respondWith({ ok: true, json: async () => ({ modelVersion: 2 }) });
    const element = await create();

    expect(element.shadowRoot!.querySelector('[role="alert"]')?.textContent).toContain(
      'unbekanntes Modellformat',
    );
  });

  it('should show malformed field metadata as a loading error', async () => {
    respondWith({
      ok: true,
      json: async () => ({
        ...model,
        patientSearch: {
          ...model.patientSearch,
          fields: [{ ...model.patientSearch.fields[0], pattern: '[' }],
        },
      }),
    });
    const element = await create();

    expect(element.shadowRoot!.querySelector('[role="alert"]')?.textContent).toContain(
      'unbekanntes Modellformat',
    );
    expect(element.shadowRoot!.querySelector('form')).toBeNull();
  });

  it('should show network errors instead of remaining in loading state', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Verbindung fehlgeschlagen')));
    const element = await create();

    expect(element.shadowRoot!.querySelector('[role="alert"]')?.textContent).toContain(
      'Verbindung fehlgeschlagen',
    );
  });

  it('should display a generation failure without rendering a form', async () => {
    respondWith({
      ok: true,
      json: async () => ({
        modelVersion: 1,
        country: { code: 'XA' },
        generationError: { code: 'PROFILE_MISMATCH', message: 'xa.xml: country fehlt.' },
      }),
    });
    const element = await create('ism/XA.json');

    expect(element.shadowRoot!.querySelector('[role="alert"]')?.textContent).toContain(
      'PROFILE_MISMATCH',
    );
    expect(element.shadowRoot!.querySelector('form')).toBeNull();
  });
});
