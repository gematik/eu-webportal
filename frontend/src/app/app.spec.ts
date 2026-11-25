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
import { provideRouter, Router } from '@angular/router';
import { App } from './app';
import { routes } from './app.routes';
import type { IsmApplication } from '../web-components/ism-patient-search/ism-application';
import { countries } from '../web-components/ism-patient-search/countries';
import { mockFlagCanvas } from '../../testing/flag-canvas';

describe('App', () => {
  beforeEach(async () => {
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
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter(routes)],
    }).compileComponents();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('should render portal navigation, scroll region, and footer landmarks', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const element: HTMLElement = fixture.nativeElement;

    expect(element.querySelector('.skip-link')?.getAttribute('href')).toBe('#main-content');
    expect(element.querySelector('header nav')?.getAttribute('aria-label')).toBe('Hauptnavigation');
    expect(element.querySelector('.portal-name')?.getAttribute('aria-label')).toBe(
      'EU-Webportal – Startseite',
    );
    expect(element.querySelector('header img')?.getAttribute('src')).toBe('Gematik_Logo_Flag.png');
    expect(
      Array.from(element.querySelectorAll('header img'), (image) => ({
        src: image.getAttribute('src'),
        alt: image.getAttribute('alt'),
      })),
    ).toEqual([{ src: 'Gematik_Logo_Flag.png', alt: 'gematik' }]);
    expect(element.querySelector('.footer-demonstrator')?.textContent).toBe(
      'MVP1 · ISM-Demonstrator',
    );
    expect(element.querySelector('main#main-content')?.getAttribute('tabindex')).toBe('-1');
    expect(element.querySelector('footer')?.textContent).toContain('MVP1');
    expect(element.querySelector('.footer-copyright')?.textContent).toBe(
      `© gematik GmbH ${new Date().getFullYear()}`,
    );
    const searchLink = element.querySelector('.search-link')!;
    expect(searchLink.getAttribute('aria-label')).toBe('Patientensuche öffnen');
    expect(searchLink.querySelector('svg')?.getAttribute('aria-hidden')).toBe('true');
  });

  it('should render application tile instead of ISM host at root route', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    await TestBed.inject(Router).navigateByUrl('/');
    await fixture.whenStable();
    const element: HTMLElement = fixture.nativeElement;

    expect(element.querySelector('app-home h1')?.textContent).toBe('Fachliche Anwendungen');
    expect(element.querySelector('.application-tile')?.textContent?.trim()).toBe(
      'Internationale Patientensuche',
    );
    expect(
      Array.from(element.querySelectorAll('.application-tiles span'), (tile) =>
        tile.textContent?.trim(),
      ),
    ).toEqual(['Dummy Anwendung 1', 'Dummy Anwendung 2', 'Dummy Anwendung 3', 'Dummy Anwendung 4']);
    expect(element.querySelectorAll('.application-tile')).toHaveLength(5);
    expect(element.querySelectorAll('.application-tiles a')).toHaveLength(1);
    expect(element.querySelector('app-ism-page')).toBeNull();
    expect(element.querySelector('nav a')?.hasAttribute('aria-current')).toBe(false);
  });

  it('should toggle the application menu and mark placeholders as unavailable', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const element: HTMLElement = fixture.nativeElement;
    const menu = element.querySelector('details')!;
    const toggle = menu.querySelector('summary')!;

    expect(menu.open).toBe(false);
    expect(toggle.getAttribute('aria-label')).toBe('Fachliche Anwendungen');
    toggle.click();
    expect(menu.open).toBe(true);
    expect(menu.querySelectorAll('li')).toHaveLength(5);
    expect(menu.querySelectorAll('a')).toHaveLength(1);
    expect(menu.querySelectorAll('[aria-disabled="true"]')).toHaveLength(4);
    expect(menu.textContent).toContain('Noch nicht verfügbar');
    toggle.click();
    expect(menu.open).toBe(false);
  });

  it('should close the menu with Escape and restore toggle focus', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const element: HTMLElement = fixture.nativeElement;
    const menu = element.querySelector('details')!;
    menu.open = true;
    menu.querySelector('a')!.focus();
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(menu.open).toBe(false);
    expect(document.activeElement).toBe(menu.querySelector('summary'));
  });

  it('should close the menu on outside clicks but not on inside clicks', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const element: HTMLElement = fixture.nativeElement;
    const menu = element.querySelector('details')!;
    menu.open = true;
    menu.querySelector('ul')!.click();
    expect(menu.open).toBe(true);
    element.querySelector('main')!.click();
    expect(menu.open).toBe(false);
  });

  it.each([
    ['application tile', '.application-tile'],
    ['header link', 'nav a'],
    ['search icon', '.search-link'],
  ])('should open patient search through %s', async (_name, selector) => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    await TestBed.inject(Router).navigateByUrl('/');
    await fixture.whenStable();
    const element: HTMLElement = fixture.nativeElement;
    const link = element.querySelector<HTMLAnchorElement>(selector);

    expect(link?.getAttribute('href')).toBe('/patientensuche');
    if (selector === 'nav a') {
      element.querySelector('summary')!.click();
      expect(element.querySelector('details')!.open).toBe(true);
    }
    link?.click();
    await fixture.whenStable();

    expect(element.querySelector('details')!.open).toBe(false);
    expect(TestBed.inject(Router).url).toBe('/patientensuche');
    expect(element.querySelector('ism-application')).toBeNull();
    expect(element.querySelector('app-ism-intro h1')?.textContent).toBe('E-Rezept-Einlösung');
    element.querySelector<HTMLAnchorElement>('app-ism-intro a')!.click();
    await fixture.whenStable();
    expect(TestBed.inject(Router).url).toBe('/patientensuche/suche');
    const application = element.querySelector<IsmApplication>('ism-application')!;
    await application.updateComplete;
    const content = application.shadowRoot!;
    expect(content.querySelector('h1')?.textContent).toBe('E-Rezept-Einlösung');
    expect(element.querySelector('nav a')?.getAttribute('aria-current')).toBe('page');
    expect(content.querySelector('ism-patient-search')).toBeNull();
    expect(content.querySelectorAll('li')).toHaveLength(26);
    expect(content.textContent).toContain('Frankreich');
    expect(content.textContent).not.toContain('Schweiz');
    content.querySelector<HTMLButtonElement>('button[data-country="PL"]')!.click();
    await fixture.whenStable();
    expect(TestBed.inject(Router).url).toBe('/patientensuche/PL');
    const selected = element.querySelector<IsmApplication>('ism-application')!;
    await selected.updateComplete;
    expect(
      selected.shadowRoot!.querySelector('ism-patient-search')?.getAttribute('model-url'),
    ).toBe('ism/PL.json');
  });

  it('should allow direct access to patient search and return through portal link', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    await TestBed.inject(Router).navigateByUrl('/patientensuche');
    await fixture.whenStable();
    const element: HTMLElement = fixture.nativeElement;

    expect(element.querySelector('app-ism-intro')).not.toBeNull();
    element.querySelector<HTMLAnchorElement>('.portal-name')?.click();
    await fixture.whenStable();

    expect(TestBed.inject(Router).url).toBe('/');
    expect(element.querySelector('app-home')).not.toBeNull();
    expect(element.querySelector('nav a')?.hasAttribute('aria-current')).toBe(false);
  });

  it('should return to the introduction when cancelling patient search', async () => {
    const fixture = TestBed.createComponent(App);
    await fixture.whenStable();
    const router = TestBed.inject(Router);
    await router.navigateByUrl('/patientensuche/PL');
    await fixture.whenStable();
    const element: HTMLElement = fixture.nativeElement;
    element
      .querySelector('ism-application')!
      .dispatchEvent(new CustomEvent('search-cancel', { bubbles: true, composed: true }));
    await fixture.whenStable();
    expect(router.url).toBe('/patientensuche');
    expect(element.querySelector('app-ism-intro')).not.toBeNull();
    await router.navigateByUrl('/patientensuche/suche');
    await fixture.whenStable();
    expect(element.querySelector('ism-application')?.getAttribute('country')).toBe('');
  });
});
