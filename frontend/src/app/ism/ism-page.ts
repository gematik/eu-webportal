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

import { ChangeDetectionStrategy, Component, CUSTOM_ELEMENTS_SCHEMA, inject } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { map } from 'rxjs';
import '../../web-components/ism-patient-search/ism-application';
import { webappSettings } from '../webapp-settings';

/**
 * Verbindet die frameworkunabhaengige ISM-Web-Component mit dem Angular-Router.
 * Die Seite synchronisiert URL und Laenderauswahl, damit Direktlinks und
 * Browsernavigation funktionieren, ohne Angular in die Fachkomponente zu ziehen.
 */
@Component({
  selector: 'app-ism-page',
  changeDetection: ChangeDetectionStrategy.OnPush,
  schemas: [CUSTOM_ELEMENTS_SCHEMA],
  templateUrl: './ism-page.html',
})
export class IsmPage {
  protected readonly flagDisplay = webappSettings.flagDisplay;
  private readonly router = inject(Router);
  protected readonly country = toSignal(
    inject(ActivatedRoute).paramMap.pipe(map((params) => params.get('country') ?? '')),
    { initialValue: '' },
  );

  protected onCountryChange(event: Event): void {
    if (!(event instanceof CustomEvent) || typeof event.detail !== 'string') {
      return;
    }
    void this.router.navigate(
      event.detail ? ['/patientensuche', event.detail] : ['/patientensuche/suche'],
    );
  }

  protected onSearchCancel(): void {
    void this.router.navigate(['/patientensuche']);
  }
}
