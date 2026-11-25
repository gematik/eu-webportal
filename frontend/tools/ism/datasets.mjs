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

import { readFile, realpath } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { IsmGenerationError } from './errors.mjs';
import { sourceCountryCode } from './parse-ism.mjs';

const ISM_DIR = fileURLToPath(new URL('../../ism/', import.meta.url));
/** Returns the isolated output directory for the selected dataset profile. */
export function datasetOutputDirectory(profile = 'public') {
  assertProfile(profile);
  return path.join(ISM_DIR, profile, 'generated');
}

function assertProfile(profile) {
  if (!['public', 'internal'].includes(profile)) {
    throw configError(`Unknown dataset profile: ${profile}`);
  }
}

// Curated labels stay independent of frontend TypeScript and optional private sources.
const INTERNAL_COUNTRIES = [
  ['AT', 'Österreich'],
  ['CY', 'Zypern'],
  ['CZ', 'Tschechien'],
  ['DK', 'Dänemark'],
  ['EE', 'Estland'],
  ['ES', 'Spanien'],
  ['FI', 'Finnland'],
  ['HR', 'Kroatien'],
  ['HU', 'Ungarn'],
  ['IE', 'Irland'],
  ['IT', 'Italien'],
  ['LT', 'Litauen'],
  ['LU', 'Luxemburg'],
  ['LV', 'Lettland'],
  ['MT', 'Malta'],
  ['NL', 'Niederlande'],
  ['NO', 'Norwegen'],
  ['PT', 'Portugal'],
  ['RO', 'Rumänien'],
  ['SE', 'Schweden'],
  ['SI', 'Slowenien'],
  ['SK', 'Slowakei'],
  ['PL', 'Polen'],
  ['GR', 'Griechenland'],
  ['IS', 'Island'],
  ['FR', 'Frankreich'],
];

/**
 * Loads a profile or explicit dataset config without changing source files.
 * Config paths are relative to their config directory and cannot escape it.
 * Each countries entry has code, name, source and an optional SVG flag.
 * Help images are inline in source XML. Internal uses the curated source list.
 */
export async function readDataset({ profile = 'public', configPath } = {}) {
  assertProfile(profile);
  const internal = profile === 'internal' && !configPath;
  const directory = internal
    ? path.join(ISM_DIR, 'internal')
    : path.dirname(path.resolve(configPath ?? path.join(ISM_DIR, 'public', 'dataset.json')));
  const config = internal
    ? {
        countries: INTERNAL_COUNTRIES.map(([code, name]) => ({
          code,
          name,
          source: `sources/${code.toLowerCase()}.xml`,
        })),
      }
    : await readConfig(configPath ?? path.join(directory, 'dataset.json'));
  validateConfig(config);
  return Promise.all(config.countries.map((country) => readCountry(directory, country)));
}

async function readConfig(file) {
  const content = await readFile(file, 'utf8');
  try {
    return JSON.parse(content);
  } catch (error) {
    throw configError(`${file}: invalid JSON (${error.message})`);
  }
}

function validateConfig(config) {
  if (!Array.isArray(config?.countries) || config.countries.length === 0) {
    throw configError('Expected a nonempty countries array.');
  }
  const codes = new Set();
  for (const country of config.countries) {
    if (
      !country ||
      typeof country.code !== 'string' ||
      !/^[A-Z]{2}$/.test(country.code ?? '') ||
      typeof country.name !== 'string' ||
      !country.name.trim()
    ) {
      throw configError('Each country needs a two-letter code and a name.');
    }
    if (codes.has(country.code)) {
      throw configError(`Duplicate country code: ${country.code}`);
    }
    codes.add(country.code);
    if (country.help !== undefined) {
      throw configError(`${country.code}: embed help media directly in source XML.`);
    }
  }
}

async function readCountry(directory, country) {
  const originalXml = (await readAsset(directory, country.source)).toString('utf8');
  if (sourceCountryCode(originalXml, country.source) !== country.code) {
    throw configError(`${country.source}: country code differs from ${country.code}.`);
  }
  const extraMedia = [];
  if (country.flag !== undefined) {
    if (typeof country.flag !== 'string' || path.extname(country.flag).toLowerCase() !== '.svg') {
      throw configError(`${country.code}: flag must be an SVG file.`);
    }
    extraMedia.push({
      file: `${country.code}-flag.svg`,
      content: await readAsset(directory, country.flag),
    });
  }
  return {
    origin: country.source,
    xml: originalXml,
    originalXml,
    name: country.name,
    extraMedia,
    ...(country.flag ? { flag: `ism/${country.code}-flag.svg` } : {}),
  };
}

async function readAsset(directory, file) {
  if (typeof file !== 'string' || !file || path.isAbsolute(file)) {
    throw configError('Asset paths must be nonempty relative file paths.');
  }
  const root = await realpath(directory);
  const target = path.resolve(root, file);
  assertContained(root, target);
  const resolved = await realpath(target);
  assertContained(root, resolved);
  return readFile(resolved);
}

function assertContained(root, target) {
  const relative = path.relative(root, target);
  if (
    !relative ||
    relative === '..' ||
    relative.startsWith(`..${path.sep}`) ||
    path.isAbsolute(relative)
  ) {
    throw configError(`Asset path escapes dataset directory: ${target}`);
  }
}

function configError(message) {
  return new IsmGenerationError('DATASET_INVALID', message);
}
