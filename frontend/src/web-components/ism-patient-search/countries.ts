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

export interface IsmCountry {
  code: string;
  name: string;
  flag?: string;
}

export function isIsmCountryList(value: unknown): value is IsmCountry[] {
  if (!Array.isArray(value) || value.length === 0) {
    return false;
  }
  const codes = new Set<string>();
  return value.every((item: unknown) => {
    if (typeof item !== 'object' || item === null) {
      return false;
    }
    const country = item as Record<string, unknown>;
    const code = country['code'];
    const flag = country['flag'];
    if (
      typeof code !== 'string' ||
      !/^[A-Z]{2}$/.test(code) ||
      codes.has(code) ||
      typeof country['name'] !== 'string' ||
      country['name'].trim().length === 0 ||
      (flag !== undefined &&
        (typeof flag !== 'string' || !/^ism\/[A-Za-z0-9_-]+\.(svg|png)$/.test(flag))) ||
      (code.startsWith('X') && flag === undefined)
    ) {
      return false;
    }
    codes.add(code);
    return true;
  });
}

export const countries: IsmCountry[] = [
  { code: 'AT', name: 'Österreich' },
  { code: 'CY', name: 'Zypern' },
  { code: 'CZ', name: 'Tschechien' },
  { code: 'DK', name: 'Dänemark' },
  { code: 'EE', name: 'Estland' },
  { code: 'ES', name: 'Spanien' },
  { code: 'FI', name: 'Finnland' },
  { code: 'HR', name: 'Kroatien' },
  { code: 'HU', name: 'Ungarn' },
  { code: 'IE', name: 'Irland' },
  { code: 'IT', name: 'Italien' },
  { code: 'LT', name: 'Litauen' },
  { code: 'LU', name: 'Luxemburg' },
  { code: 'LV', name: 'Lettland' },
  { code: 'MT', name: 'Malta' },
  { code: 'NL', name: 'Niederlande' },
  { code: 'NO', name: 'Norwegen' },
  { code: 'PT', name: 'Portugal' },
  { code: 'RO', name: 'Rumänien' },
  { code: 'SE', name: 'Schweden' },
  { code: 'SI', name: 'Slowenien' },
  { code: 'SK', name: 'Slowakei' },
  { code: 'PL', name: 'Polen' },
  { code: 'GR', name: 'Griechenland' },
  { code: 'IS', name: 'Island' },
  { code: 'FR', name: 'Frankreich' },
].sort((left, right) => left.name.localeCompare(right.name, 'de'));
