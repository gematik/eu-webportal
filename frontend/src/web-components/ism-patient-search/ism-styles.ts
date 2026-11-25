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

import { css } from 'lit';

export const ismStyles = css`
  :host {
    --ism-primary: var(--portal-primary, #000e52);
    --ism-accent: var(--portal-accent, #00ef8b);
    --ism-text: var(--portal-text, #17191c);
    --ism-muted: var(--portal-muted, #505665);
    --ism-surface: var(--portal-surface, #fff);
    --ism-border: var(--portal-border, #8d96ad);
    --ism-link: var(--portal-link, #24599b);
    --ism-disabled: var(--portal-disabled, #d5e0ee);
    --ism-error: var(--portal-error, #a51d2d);
    color: var(--ism-text);
    font-family: var(--portal-font, system-ui, sans-serif);
    line-height: 1.5;
  }
  *,
  *::before,
  *::after {
    box-sizing: border-box;
  }
  button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    min-height: 2.75rem;
    padding: 0.5rem 1rem;
    border: 1px solid var(--ism-primary);
    border-radius: 999px;
    background: var(--ism-surface);
    color: var(--ism-primary);
    font: inherit;
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
  }
  button:hover:not(:disabled) {
    background: var(--portal-footer, #e9eef5);
  }
  button:focus-visible,
  summary:focus-visible,
  input:focus-visible,
  select:focus-visible {
    outline: 0.125rem solid var(--ism-primary);
    outline-offset: 0.2rem;
  }
  [role='alert'] {
    color: var(--ism-error);
  }
`;
