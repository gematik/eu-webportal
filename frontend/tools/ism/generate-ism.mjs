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

import { parseArgs } from 'node:util';
import { pathToFileURL } from 'node:url';
import { IsmGenerationError } from './errors.mjs';
import { datasetOutputDirectory, readDataset } from './datasets.mjs';
import { parseIsm, sourceCountryCode } from './parse-ism.mjs';
import { readFileSource } from './sources.mjs';
import { sha256, writeOutput } from './write-output.mjs';

/**
 * Erzeugt aus ISM-Quellen das Anzeigemodell samt Hilfsmedien.
 * Standardmaessig verhindern Profilfehler die Ausgabe. Der explizite
 * Diagnosemodus schreibt stattdessen Fehlerartefakte fuer zuordenbare Laender.
 */
export async function generateIsm({ sources, outDir, diagnostics = false }) {
  if (sources.length === 0) {
    throw new IsmGenerationError('NO_SOURCES', 'Keine ISM-Quelle gefunden.');
  }
  const entries = sources.map((source) => prepareSource(source, diagnostics));
  const unique = diagnostics ? deduplicateIdenticalSources(entries) : entries;
  assertUniqueCountries(unique);
  return writeOutput(outDir, unique);
}

function prepareSource({ origin, xml, originalXml, name, flag, extraMedia = [] }, diagnostics) {
  const sourceSha256 = sha256(originalXml ?? xml);
  try {
    const entry = parseIsm(xml, origin);
    return { ...entry, media: [...entry.media, ...extraMedia], origin, sourceSha256, name, flag };
  } catch (error) {
    if (!diagnostics || !(error instanceof IsmGenerationError)) {
      throw error;
    }
    const code = sourceCountryCode(xml, origin);
    console.warn(`ISM_UNAVAILABLE: ${error.message}`);
    return {
      origin,
      sourceSha256,
      media: extraMedia,
      name,
      flag,
      model: {
        modelVersion: 1,
        country: { code },
        generationError: { code: error.code, message: error.message },
      },
    };
  }
}

/**
 * Generates a dataset into its profile's generated directory.
 * An explicit config replaces the selected profile's built-in configuration.
 * countries.json is a manifest-tracked array of { code, name, flag? }.
 * Flag URLs are base-relative ism/<code>-flag.svg paths.
 * npm start and build regenerate public through their lifecycle hooks.
 * npm start:internal and build:internal bypass those hooks after generation.
 */
export async function generateDataset({
  profile = 'public',
  configPath,
  outDir,
  diagnostics = false,
} = {}) {
  return generateIsm({
    sources: await readDataset({ profile, configPath }),
    outDir: outDir ?? datasetOutputDirectory(profile),
    diagnostics,
  });
}

function deduplicateIdenticalSources(entries) {
  return entries.filter((entry, index) => {
    const earlier = entries
      .slice(0, index)
      .find(
        (other) =>
          other.model.country.code === entry.model.country.code &&
          other.sourceSha256 === entry.sourceSha256,
      );
    if (earlier) {
      console.warn(
        `DUPLICATE_SOURCE: ${entry.origin} entspricht ${earlier.origin}; nur eine Maske wird ausgegeben.`,
      );
    }
    return !earlier;
  });
}

function assertUniqueCountries(entries) {
  const codes = entries.map((entry) => entry.model.country.code);
  const duplicate = codes.find((code, index) => codes.indexOf(code) !== index);
  if (duplicate) {
    throw new IsmGenerationError('DUPLICATE_COUNTRY', `Land ${duplicate} wird mehrfach geliefert.`);
  }
}

async function main() {
  const { values } = parseArgs({
    options: {
      source: { type: 'string' },
      profile: { type: 'string' },
      config: { type: 'string' },
      out: { type: 'string' },
      diagnostics: { type: 'boolean', default: false },
    },
  });
  if (values.source && (values.profile || values.config || !values.out)) {
    throw new IsmGenerationError(
      'USAGE',
      'Use --profile public|internal [--config dataset.json] [--out directory] or --source file.xml --out directory.',
    );
  }
  const outDir = values.out ?? datasetOutputDirectory(values.profile);
  const manifest = values.source
    ? await generateIsm({
        sources: await readFileSource(values.source),
        outDir,
        diagnostics: values.diagnostics,
      })
    : await generateDataset({
        profile: values.profile,
        configPath: values.config,
        outDir,
        diagnostics: values.diagnostics,
      });
  console.log(
    `ISM-Artefakte: ${manifest.countries.map((country) => `${country.code} (${country.status})`).join(', ')} -> ${outDir}`,
  );
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(error instanceof IsmGenerationError ? error.message : error);
    process.exitCode = 1;
  });
}
