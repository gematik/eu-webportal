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

import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

/** Einstiegsseite fuer die Einloesung europaeischer E-Rezepte. */
@Component({
  selector: 'app-ism-intro',
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section aria-labelledby="intro-heading">
      <h1 id="intro-heading">E-Rezept-Einlösung</h1>
      <p>Einlösung von europäischen E-Rezepten über das Apothekenportal</p>
      <a routerLink="/patientensuche/suche"
        >Patientensuche starten <span aria-hidden="true">→</span></a
      >
    </section>
  `,
  styles: `
    :host {
      display: block;
      max-width: var(--portal-content-width);
      margin-inline: auto;
    }
    h1 {
      margin: 0;
      color: var(--portal-primary);
      font-size: 2rem;
      line-height: 1.25;
      font-weight: 750;
    }
    p {
      margin: 0.5rem 0 0;
      color: var(--portal-primary);
      font-size: 1.25rem;
    }
    a {
      display: inline-flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      min-height: 3rem;
      margin-top: 7rem;
      padding: 0.75rem 2rem;
      border-radius: 999px;
      background: var(--portal-primary);
      color: var(--portal-accent);
      font-size: 1.125rem;
      font-weight: 700;
      text-decoration: none;
    }
    a:focus-visible {
      outline: 0.2rem solid var(--portal-primary);
      outline-offset: 0.2rem;
    }
    a:hover {
      box-shadow: 0 0 0 0.125rem var(--portal-primary);
    }
    @media (max-width: 40rem) {
      h1 {
        font-size: 1.5rem;
      }
      p {
        font-size: 1rem;
      }
      a {
        margin-top: 4rem;
        max-width: 100%;
        font-size: 1rem;
      }
    }
  `,
})
export class IsmIntro {}
