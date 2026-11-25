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

export interface IsmField {
  readonly domain: string;
  readonly label: string;
  readonly description: string;
  readonly originalDescription: string | null;
  readonly mandatory: boolean;
  readonly pattern: string | null;
}

export interface IsmHelpMedia {
  readonly description: string | null;
  readonly file: string;
  readonly mediaType: string;
  readonly name: string;
}

export interface IsmChoiceGroup {
  readonly alternatives: readonly {
    readonly display: string;
    readonly fieldIndexes: readonly number[];
  }[];
}

export interface IsmPatientSearchModel {
  readonly modelVersion: 1;
  readonly country: { readonly code: string; readonly label: string };
  readonly patientSearch: {
    readonly friendlyName: string | null;
    readonly scope: string | null;
    readonly fields: readonly IsmField[];
    readonly choiceGroups?: readonly IsmChoiceGroup[];
    readonly helpMedia: readonly IsmHelpMedia[];
  };
}

export type FieldError = 'required' | 'pattern';

export function generationErrorMessage(value: unknown): string | null {
  if (!isRecord(value) || value['modelVersion'] !== 1 || !isRecord(value['generationError'])) {
    return null;
  }
  const error = value['generationError'];
  return typeof error['message'] === 'string' && typeof error['code'] === 'string'
    ? error['message'].startsWith(`${error['code']}:`)
      ? error['message']
      : `${error['code']}: ${error['message']}`
    : null;
}

/**
 * Prüft einen Wert gegen die ISM-Regeln des Feldes. Ohne `pattern` findet keine
 * Formatprüfung statt; eine Regel wird nicht geraten.
 */
export function validateField(field: IsmField, value: string): FieldError | null {
  if (value === '') {
    return field.mandatory ? 'required' : null;
  }
  if (field.pattern !== null && !new RegExp(`^(?:${field.pattern})$`, 'v').test(value)) {
    return 'pattern';
  }
  return null;
}

export function isIsmPatientSearchModel(value: unknown): value is IsmPatientSearchModel {
  if (!isRecord(value) || !isRecord(value['country']) || !isRecord(value['patientSearch'])) {
    return false;
  }
  const country = value['country'];
  const search = value['patientSearch'];
  return (
    value['modelVersion'] === 1 &&
    typeof country['code'] === 'string' &&
    /^[A-Z]{2}$/.test(country['code']) &&
    typeof country['label'] === 'string' &&
    isNullableString(search['friendlyName']) &&
    isNullableString(search['scope']) &&
    Array.isArray(search['fields']) &&
    search['fields'].length > 0 &&
    search['fields'].every(isField) &&
    isChoiceGroups(search['choiceGroups'], search['fields'].length) &&
    Array.isArray(search['helpMedia']) &&
    search['helpMedia'].every(isMedia)
  );
}

function isChoiceGroups(value: unknown, fieldCount: number): boolean {
  if (value === undefined) {
    return true;
  }
  if (!Array.isArray(value) || value.length === 0) {
    return false;
  }
  const used = new Set<number>();
  return value.every(
    (group: unknown) =>
      isRecord(group) &&
      Array.isArray(group['alternatives']) &&
      group['alternatives'].length > 0 &&
      group['alternatives'].every(
        (alternative: unknown) =>
          isRecord(alternative) &&
          typeof alternative['display'] === 'string' &&
          alternative['display'].trim().length > 0 &&
          Array.isArray(alternative['fieldIndexes']) &&
          alternative['fieldIndexes'].length > 0 &&
          alternative['fieldIndexes'].every((index: unknown) => {
            if (
              typeof index !== 'number' ||
              !Number.isInteger(index) ||
              index < 0 ||
              index >= fieldCount ||
              used.has(index)
            ) {
              return false;
            }
            used.add(index);
            return true;
          }),
      ),
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string';
}

function isField(value: unknown): value is IsmField {
  if (!isRecord(value)) {
    return false;
  }
  return (
    typeof value['domain'] === 'string' &&
    value['domain'].length > 0 &&
    typeof value['label'] === 'string' &&
    typeof value['description'] === 'string' &&
    isNullableString(value['originalDescription']) &&
    typeof value['mandatory'] === 'boolean' &&
    isPattern(value['pattern'])
  );
}

function isPattern(value: unknown): value is string | null {
  if (value === null) {
    return true;
  }
  if (typeof value !== 'string') {
    return false;
  }
  try {
    new RegExp(`^(?:${value})$`, 'v');
    return true;
  } catch {
    return false;
  }
}

function isMedia(value: unknown): value is IsmHelpMedia {
  return (
    isRecord(value) &&
    isNullableString(value['description']) &&
    typeof value['file'] === 'string' &&
    /^[A-Za-z0-9_-]+\.(jpg|png)$/.test(value['file']) &&
    (value['mediaType'] === 'image/jpeg' || value['mediaType'] === 'image/png') &&
    typeof value['name'] === 'string'
  );
}
