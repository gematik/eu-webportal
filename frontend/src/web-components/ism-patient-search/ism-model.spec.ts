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

import { IsmField, isIsmPatientSearchModel, validateField } from './ism-model';

const field = (overrides: Partial<IsmField> = {}): IsmField => ({
  domain: '1.2.3',
  label: 'label.ism.id',
  description: 'Example identifier',
  originalDescription: null,
  mandatory: true,
  pattern: '^[A-Z]{2}$',
  ...overrides,
});

describe('validateField', () => {
  it('should accept a value matching the whole pattern', () => {
    expect(validateField(field(), 'AB')).toBeNull();
  });

  it.each(['A', 'ABC', '12', 'AB\n'])('should report pattern error for %j', (value) => {
    expect(validateField(field(), value)).toBe('pattern');
  });

  it('should require a value for mandatory fields', () => {
    expect(validateField(field(), '')).toBe('required');
  });

  it('should accept an empty optional field', () => {
    expect(validateField(field({ mandatory: false }), '')).toBeNull();
  });

  it('should not check the format when the ISM provides no pattern', () => {
    expect(validateField(field({ pattern: null }), 'anything')).toBeNull();
  });

  it('should treat alternatives in a pattern as a whole', () => {
    expect(validateField(field({ pattern: 'a|b' }), 'ab')).toBe('pattern');
  });
});

describe('isIsmPatientSearchModel', () => {
  const model = {
    modelVersion: 1,
    country: { code: 'XA', label: 'label' },
    patientSearch: { friendlyName: null, scope: 'ALL', fields: [field()], helpMedia: [] },
  };

  it('should accept the generated model shape', () => {
    expect(isIsmPatientSearchModel(model)).toBe(true);
  });

  it('should accept separate fields sharing a domain', () => {
    expect(
      isIsmPatientSearchModel({
        ...model,
        patientSearch: { ...model.patientSearch, fields: [field(), field()] },
      }),
    ).toBe(true);
  });

  it('should accept indexed CHOICE alternatives', () => {
    expect(
      isIsmPatientSearchModel({
        ...model,
        patientSearch: {
          ...model.patientSearch,
          fields: [field(), field()],
          choiceGroups: [
            {
              alternatives: [
                { display: 'First', fieldIndexes: [0] },
                { display: 'Second', fieldIndexes: [1] },
              ],
            },
          ],
        },
      }),
    ).toBe(true);
  });

  it.each(
    [
      null,
      [],
      [{}],
      [{ alternatives: [] }],
      [{ alternatives: [{ display: '', fieldIndexes: [0] }] }],
      [{ alternatives: [{ display: 'x', fieldIndexes: [] }] }],
      [{ alternatives: [{ display: 'x', fieldIndexes: [-1] }] }],
      [{ alternatives: [{ display: 'x', fieldIndexes: [1] }] }],
      [{ alternatives: [{ display: 'x', fieldIndexes: [0.5] }] }],
      [{ alternatives: [{ display: 'x', fieldIndexes: [0, 0] }] }],
      [
        { alternatives: [{ display: 'x', fieldIndexes: [0] }] },
        { alternatives: [{ display: 'y', fieldIndexes: [0] }] },
      ],
    ].map((choiceGroups) => [choiceGroups]),
  )('should reject malformed CHOICE metadata %j', (choiceGroups) => {
    expect(
      isIsmPatientSearchModel({
        ...model,
        patientSearch: { ...model.patientSearch, choiceGroups },
      }),
    ).toBe(false);
  });

  it.each([null, {}, { ...model, modelVersion: 2 }, { ...model, patientSearch: {} }])(
    'should reject %j',
    (value) => {
      expect(isIsmPatientSearchModel(value)).toBe(false);
    },
  );

  it.each([
    { fields: [] },
    { fields: [null] },
    { fields: [field({ pattern: '[' })] },
    { fields: [{ ...field(), mandatory: 'true' }] },
    { helpMedia: [{ description: null, name: 'x', mediaType: 'image/jpeg', file: '../x.jpg' }] },
  ])('should reject malformed search metadata %j', (search) => {
    expect(
      isIsmPatientSearchModel({
        ...model,
        patientSearch: { ...model.patientSearch, ...search },
      }),
    ).toBe(false);
  });
});
