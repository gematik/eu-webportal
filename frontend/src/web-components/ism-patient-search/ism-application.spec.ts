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

import './ism-application';
import type { IsmApplication } from './ism-application';
import { countries } from './countries';
import { mockFlagCanvas } from '../../../testing/flag-canvas';

describe('IsmApplication', () => {
  beforeEach(() => {
    mockFlagCanvas();
  });

  afterEach(() => {
    document.body.replaceChildren();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  async function create(country = '') {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    const element = document.createElement('ism-application') as IsmApplication;
    element.country = country;
    document.body.append(element);
    await element.updateComplete;
    return element;
  }

  it('should keep country selection and search on one page without Angular', async () => {
    const element = await create();
    const changed = vi.fn();
    element.addEventListener('country-change', changed);
    expect(element.shadowRoot!.querySelectorAll('li')).toHaveLength(26);
    expect(element.shadowRoot!.querySelector('ism-patient-search')).toBeNull();
    element.shadowRoot!.querySelector<HTMLButtonElement>('button[data-country="PL"]')!.click();
    await element.updateComplete;
    expect(element.country).toBe('PL');
    expect(changed.mock.calls[0][0].detail).toBe('PL');
    expect(changed.mock.calls[0][0].composed).toBe(true);
    expect(element.shadowRoot!.querySelector('ism-patient-search')?.getAttribute('model-url')).toBe(
      'ism/PL.json',
    );
    expect(element.shadowRoot!.querySelector('details')!.open).toBe(false);
    expect(element.shadowRoot!.querySelector('summary')?.textContent).toContain('Polen');
    element.shadowRoot!.querySelector<HTMLButtonElement>('button[data-country="FR"]')!.click();
    await element.updateComplete;
    expect(element.country).toBe('FR');
    expect(element.shadowRoot!.querySelector('ism-patient-search')?.getAttribute('model-url')).toBe(
      'ism/FR.json',
    );
    expect(element.shadowRoot!.querySelector('details')).not.toBeNull();
  });

  it('should describe patient search independently of its decorative icon', async () => {
    const element = await create();
    const heading = element.shadowRoot!.querySelector('.search-heading')!;
    expect(heading.querySelector('h2')?.textContent).toBe('Patientensuche');
    expect(heading.querySelector('p')?.textContent).toContain('auf E-Rezepte zuzugreifen');
    expect(heading.querySelector('.search-icon')?.getAttribute('aria-hidden')).toBe('true');
    expect(element.shadowRoot!.querySelector('section')?.getAttribute('aria-labelledby')).toBe(
      'ism-heading',
    );
  });

  it('should emit cancellation for returning to the introduction', async () => {
    const element = await create('PL');
    const cancelled = vi.fn();
    element.addEventListener('search-cancel', cancelled);
    element.shadowRoot!.querySelector<HTMLButtonElement>('.back')!.click();
    expect(cancelled).toHaveBeenCalledOnce();
    expect(cancelled.mock.calls[0][0].composed).toBe(true);
  });

  it('should place the back button inside the search action slot without duplicating it', async () => {
    const element = await create('PL');
    const root = element.shadowRoot!;
    const search = root.querySelector('ism-patient-search')!;
    expect(root.querySelectorAll('.back')).toHaveLength(1);
    expect(search.querySelector('.back')?.getAttribute('slot')).toBe('back');
  });

  it('should keep back navigation available before selecting a country', async () => {
    const element = await create();
    expect(element.shadowRoot!.querySelectorAll('.back')).toHaveLength(1);
    expect(element.shadowRoot!.querySelector('.back')?.closest('ism-patient-search')).toBeNull();
  });

  it('should close country selection with Escape and restore focus', async () => {
    const element = await create();
    const selection = element.shadowRoot!.querySelector('details')!;
    selection.open = true;
    selection
      .querySelector('button')!
      .dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(selection.open).toBe(false);
    expect(element.shadowRoot!.activeElement).toBe(selection.querySelector('summary'));
  });

  it.each(['GR', 'IS', 'FR'])('should open a selected country %s', async (country) => {
    const element = await create(country);
    expect(element.shadowRoot!.querySelector('ism-patient-search')?.getAttribute('model-url')).toBe(
      `ism/${country}.json`,
    );
  });

  it('should show decorative emoji flags by default', async () => {
    const element = await create();
    expect(element.shadowRoot!.querySelector('input[type="checkbox"]')).toBeNull();
    expect(element.shadowRoot!.querySelectorAll('li img')).toHaveLength(0);
    const flag = element.shadowRoot!.querySelector('[data-country="PL"] .country-emoji')!;
    expect(flag.textContent).toBe(String.fromCodePoint(0x1f1f5, 0x1f1f1));
    expect(flag.getAttribute('aria-hidden')).toBe('true');
  });

  it('should automatically fall back to decorative SVGs when emoji flags are unsupported', async () => {
    vi.mocked(HTMLCanvasElement.prototype.getContext).mockReturnValue(null);
    const element = await create();
    expect(element.flagDisplay).toBe('auto');
    for (const country of countries) {
      const button = element.shadowRoot!.querySelector(`button[data-country="${country.code}"]`)!;
      const image = button.querySelector('img')!;
      expect(image.getAttribute('src')).toBe(`flags/${country.code.toLowerCase()}.svg`);
      expect(image.alt).toBe('');
      expect(button.firstElementChild).toBe(image);
      expect(button.textContent).toContain(country.name);
    }
  });

  it('should support configuring SVG mode through an attribute', async () => {
    const element = await create();
    element.setAttribute('flag-display', 'svg');
    await element.updateComplete;
    expect(element.shadowRoot!.querySelectorAll('li img')).toHaveLength(countries.length);
  });

  it('should support explicitly forcing emoji display through configuration', async () => {
    vi.mocked(HTMLCanvasElement.prototype.getContext).mockReturnValue(null);
    const element = await create();
    element.flagDisplay = 'emoji';
    await element.updateComplete;
    expect(element.shadowRoot!.querySelectorAll('.country-emoji')).toHaveLength(countries.length);
    expect(element.shadowRoot!.querySelector('li img')).toBeNull();
  });

  it('should always use configured images for fictional countries', async () => {
    const element = await create();
    element.countryOptions = [
      { code: 'XA', name: 'Aveloria', flag: 'ism-demo/01_aveloria_flag.svg' },
    ];
    await element.updateComplete;
    const button = element.shadowRoot!.querySelector('[data-country="XA"]')!;
    expect(button.querySelector('img')?.getAttribute('src')).toBe('ism-demo/01_aveloria_flag.svg');
    expect(button.querySelector('.country-emoji')).toBeNull();
    expect(button.textContent).toContain('Aveloria');
  });

  it('should load only the countries from the selected dataset', async () => {
    const element = await create();
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify([{ code: 'XA', name: 'Aveloria', flag: 'ism/XA-flag.svg' }])),
    );
    element.countriesUrl = 'ism/countries.json';
    await vi.waitFor(() => {
      expect(element.shadowRoot!.querySelector('[data-country="XA"]')).not.toBeNull();
    });
    expect(element.shadowRoot!.querySelector('[data-country="PL"]')).toBeNull();
  });

  it.each(['http', 'invalid'])(
    'should show an error without falling back to real countries for %s failure',
    async (failure) => {
      const element = await create();
      vi.spyOn(console, 'error').mockImplementation(() => {});
      vi.mocked(fetch).mockResolvedValue(
        failure === 'http'
          ? new Response('', { status: 404 })
          : new Response(JSON.stringify([{ code: 'XA', name: 'Missing flag' }])),
      );
      element.countriesUrl = 'ism/countries.json';
      await vi.waitFor(() => {
        expect(element.shadowRoot!.querySelector('[role="alert"]')).not.toBeNull();
      });
      expect(element.shadowRoot!.querySelectorAll('li')).toHaveLength(0);
    },
  );

  it('should reject an unknown country without loading a search mask', async () => {
    const element = await create('CH');
    expect(element.shadowRoot!.querySelector('[role="alert"]')?.textContent).toContain(
      'keine Suchmaske',
    );
    expect(element.shadowRoot!.querySelector('ism-patient-search')).toBeNull();
    expect(fetch).not.toHaveBeenCalled();
  });
});
