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

export type FlagDisplay = 'auto' | 'emoji' | 'svg';

export function countryFlagEmoji(code: string): string {
  return String.fromCodePoint(...Array.from(code, (letter) => 0x1f1e6 + letter.charCodeAt(0) - 65));
}

/**
 * Detects a combined flag glyph rather than two separate regional letters.
 * Browsers expose no definitive emoji capability API, so this is a heuristic.
 */
export function supportsFlagEmoji(code: string): boolean {
  const context = document.createElement('canvas').getContext('2d');
  if (!context) {
    return false;
  }
  context.font = '32px "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif';
  const emoji = countryFlagEmoji(code);
  const letters = Array.from(emoji);
  const combinedWidth = context.measureText(emoji).width;
  const separateWidth = letters.reduce(
    (width, letter) => width + context.measureText(letter).width,
    0,
  );
  return combinedWidth > 0 && combinedWidth < separateWidth * 0.9;
}
