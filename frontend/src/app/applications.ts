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

export interface PortalApplication {
  readonly name: string;
  readonly route: string | null;
}

export const applications: readonly PortalApplication[] = [
  { name: 'Internationale Patientensuche', route: '/patientensuche' },
  { name: 'Dummy Anwendung 1', route: null },
  { name: 'Dummy Anwendung 2', route: null },
  { name: 'Dummy Anwendung 3', route: null },
  { name: 'Dummy Anwendung 4', route: null },
];
