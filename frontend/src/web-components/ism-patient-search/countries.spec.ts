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

import { countries, isIsmCountryList } from './countries';

describe('countries', () => {
  it('should accept real countries and fictional countries with explicit images', () => {
    expect(
      isIsmCountryList([
        { code: 'PL', name: 'Polen' },
        { code: 'XA', name: 'Aveloria', flag: 'ism/XA-flag.svg' },
      ]),
    ).toBe(true);
  });

  it.each(
    [
      null,
      [],
      [{ code: 'pl', name: 'Polen' }],
      [{ code: 'PL', name: '' }],
      [{ code: 'XA', name: 'Aveloria' }],
      [{ code: 'PL', name: 'Polen', flag: 'https://example.com/flag.svg' }],
      [{ code: 'PL', name: 'Polen', flag: 'ism/../private.svg' }],
      [
        { code: 'PL', name: 'Polen' },
        { code: 'PL', name: 'Duplicate' },
      ],
    ].map((value) => [value]),
  )('should reject invalid country configuration %#', (value) => {
    expect(isIsmCountryList(value)).toBe(false);
  });

  it('should include every source country except Switzerland and Germany without duplicate Greece', () => {
    expect(countries.map((country) => country.code).sort()).toEqual([
      'AT',
      'CY',
      'CZ',
      'DK',
      'EE',
      'ES',
      'FI',
      'FR',
      'GR',
      'HR',
      'HU',
      'IE',
      'IS',
      'IT',
      'LT',
      'LU',
      'LV',
      'MT',
      'NL',
      'NO',
      'PL',
      'PT',
      'RO',
      'SE',
      'SI',
      'SK',
    ]);
  });

  it('should sort German country names alphabetically', () => {
    const names = countries.map((country) => country.name);
    expect(names).toEqual([...names].sort((left, right) => left.localeCompare(right, 'de')));
    expect(names[0]).toBe('Dänemark');
    expect(names.at(-1)).toBe('Zypern');
  });
});
