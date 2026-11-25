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

import { createHash } from 'node:crypto';
import { mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import path from 'node:path';

export const MANIFEST_FILE = 'manifest.json';

export const sha256 = (content) => createHash('sha256').update(content).digest('hex');

/**
 * Schreibt Modelle und Medien deterministisch. Das Manifest enthält keine
 * Zeitstempel, damit identische Eingaben bytegleiche Ausgaben erzeugen.
 */
export async function writeOutput(outDir, entries) {
  await mkdir(outDir, { recursive: true });
  await removePreviousOutput(outDir);

  const files = [];
  for (const entry of entries) {
    const modelFile = `${entry.model.country.code}.json`;
    await writeGenerated(outDir, modelFile, `${JSON.stringify(entry.model, null, 2)}\n`, files);
    for (const media of entry.media) {
      await writeGenerated(outDir, media.file, media.content, files);
    }
  }

  const countries = entries
    .map((entry) => ({
      code: entry.model.country.code,
      name: entry.name ?? entry.model.country.code,
      ...(entry.flag ? { flag: entry.flag } : {}),
    }))
    .sort((left, right) => left.name.localeCompare(right.name, 'de'));
  await writeGenerated(outDir, 'countries.json', `${JSON.stringify(countries, null, 2)}\n`, files);

  const manifest = {
    modelVersion: entries[0]?.model.modelVersion ?? null,
    countries: entries.map((entry) => ({
      code: entry.model.country.code,
      status: entry.model.generationError ? 'unavailable' : 'available',
      ...(entry.model.generationError ? { error: entry.model.generationError } : {}),
      model: `${entry.model.country.code}.json`,
      source: { origin: entry.origin, sha256: entry.sourceSha256 },
    })),
    files,
  };
  await writeFile(path.join(outDir, MANIFEST_FILE), `${JSON.stringify(manifest, null, 2)}\n`);
  return manifest;
}

async function writeGenerated(outDir, file, content, files) {
  await writeFile(path.join(outDir, file), content);
  files.push({ path: file, sha256: sha256(content) });
}

async function removePreviousOutput(outDir) {
  let previous;
  try {
    previous = JSON.parse(await readFile(path.join(outDir, MANIFEST_FILE), 'utf8'));
  } catch (error) {
    if (error.code === 'ENOENT') {
      return;
    }
    throw error;
  }
  for (const file of previous.files ?? []) {
    await rm(path.join(outDir, path.basename(file.path)), { force: true });
  }
}
