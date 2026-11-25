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

import { countryFlagEmoji, supportsFlagEmoji } from './flag-display';

describe('flag emoji detection', () => {
  afterEach(() => vi.restoreAllMocks());

  it('should create the regional indicator pair for the country', () => {
    expect(countryFlagEmoji('PL')).toBe(String.fromCodePoint(0x1f1f5, 0x1f1f1));
  });

  it('should fall back to images when canvas is unavailable', () => {
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
    expect(supportsFlagEmoji('PL')).toBe(false);
  });

  it.each([
    [32, 32, true],
    [64, 32, false],
    [0, 0, false],
    [63, 32, false],
  ])(
    'should detect joined width %i and individual width %i as supported %s',
    (joinedWidth, individualWidth, expected) => {
      const context = {
        font: '',
        measureText: (text: string) => ({
          width: Array.from(text).length === 2 ? joinedWidth : individualWidth,
        }),
      };
      vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
        context as CanvasRenderingContext2D,
      );
      expect(supportsFlagEmoji('PL')).toBe(expected);
    },
  );
});
