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

import { TestBed } from '@angular/core/testing';
import { IsmPage } from './ism-page';
import { ActivatedRoute, convertToParamMap, provideRouter } from '@angular/router';
import { of } from 'rxjs';
import { countries } from '../../web-components/ism-patient-search/countries';
import { mockFlagCanvas } from '../../../testing/flag-canvas';
import { webappSettings } from '../webapp-settings';

describe('IsmPage', () => {
  beforeEach(() => {
    mockFlagCanvas();
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockImplementation(async (url: string) =>
          url === 'ism/countries.json'
            ? { ok: true, json: async () => countries }
            : { ok: false, status: 404 },
        ),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('should not render a search mask for an unknown country', async () => {
    await TestBed.configureTestingModule({
      imports: [IsmPage],
      providers: [
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: { paramMap: of(convertToParamMap({ country: 'XX' })) },
        },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(IsmPage);
    await fixture.whenStable();
    const element: HTMLElement = fixture.nativeElement;
    expect(element.querySelector('ism-application')?.getAttribute('country')).toBe('XX');
  });
  it('should embed the Polish patient search component', async () => {
    await TestBed.configureTestingModule({
      imports: [IsmPage],
      providers: [
        provideRouter([]),
        {
          provide: ActivatedRoute,
          useValue: { paramMap: of(convertToParamMap({ country: 'PL' })) },
        },
      ],
    }).compileComponents();
    const fixture = TestBed.createComponent(IsmPage);
    await fixture.whenStable();
    const element: HTMLElement = fixture.nativeElement;

    expect(element.querySelector('ism-application')?.getAttribute('country')).toBe('PL');
    expect(element.querySelector('ism-application')?.getAttribute('flag-display')).toBe(
      webappSettings.flagDisplay,
    );
    expect(element.querySelector('ism-application')?.getAttribute('countries-url')).toBe(
      'ism/countries.json',
    );
  });
});
