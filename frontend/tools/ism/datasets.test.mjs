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

import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';
import { datasetOutputDirectory, readDataset } from './datasets.mjs';
import { generateDataset } from './generate-ism.mjs';
import { parseIsm } from './parse-ism.mjs';
import { sha256 } from './write-output.mjs';

const PUBLIC = fileURLToPath(new URL('../../ism/public/', import.meta.url));
const CLI = fileURLToPath(new URL('./generate-ism.mjs', import.meta.url));
const execute = promisify(execFile);
const SYNTHETIC_INTERNAL = {
  code: 'ZZ',
  name: 'Synthetic internal country',
  source: 'zz.xml',
};
const SYNTHETIC_XML = `<searchFields xmlns="http://ec.europa.eu/sante/ehncp/ism">
  <country code="ZZ" label="label.ism.addressCountry"><patientSearch>
    <identifier type="NORMAL"><id domain="https://internal.example/id"
      label="label.ism.id" contextualDescription="Synthetic identifier"/></identifier>
  </patientSearch></country></searchFields>`;

async function withDirectory(callback) {
  const directory = await mkdtemp(path.join(tmpdir(), 'ism-dataset-'));
  try {
    await callback(directory);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}

async function writeConfig(directory, countries = [SYNTHETIC_INTERNAL]) {
  const configPath = path.join(directory, 'dataset.json');
  await writeFile(configPath, JSON.stringify({ countries }));
  return configPath;
}

async function readJson(file) {
  return JSON.parse(await readFile(file, 'utf8'));
}

test('default dataset emits example countries, flags and actual help image bytes', async () => {
  await withDirectory(async (outDir) => {
    const config = await readJson(path.join(PUBLIC, 'dataset.json'));
    const manifest = await generateDataset({ outDir });
    const countries = await readJson(path.join(outDir, 'countries.json'));
    assert.deepEqual(
      countries,
      config.countries.map(({ code, name }) => ({ code, name, flag: `ism/${code}-flag.svg` })),
    );
    const fieldCounts = [6, 3, 1];
    const choiceCounts = [2, 0, 0];
    for (const [index, country] of config.countries.entries()) {
      const model = await readJson(path.join(outDir, `${country.code}.json`));
      assert.equal(model.patientSearch.fields.length, fieldCounts[index]);
      assert.equal(model.patientSearch.choiceGroups?.length ?? 0, choiceCounts[index]);
      const [help] = model.patientSearch.helpMedia;
      assert.equal(model.patientSearch.helpMedia.length, 1);
      assert.equal(help.mediaType, 'image/png');
      assert.equal(help.description, `${country.name} synthetic identification example`);
      assert.equal(help.file, `${country.code}-identification-help.png`);
      assert.deepEqual(
        await readFile(path.join(outDir, help.file)),
        await readFile(
          path.join(
            PUBLIC,
            'artwork',
            [
              '04_aveloria_identification_help.png',
              '05_belvaria_identification_help.png',
              '06_caldoria_identification_help.png',
            ][index],
          ),
        ),
      );
      assert.deepEqual(
        await readFile(path.join(outDir, `${country.code}-flag.svg`)),
        await readFile(path.join(PUBLIC, country.flag)),
      );
      assert.equal(
        manifest.countries[index].source.sha256,
        sha256(await readFile(path.join(PUBLIC, country.source))),
      );
    }
    for (const file of manifest.files) {
      assert.equal(sha256(await readFile(path.join(outDir, file.path))), file.sha256);
    }
    assert.ok(manifest.files.some((file) => file.path === 'countries.json'));
    const second = await generateDataset({ outDir });
    assert.deepEqual(second, manifest);
  });
});

test('public XML physically contains help and loading leaves bytes unchanged', async () => {
  const config = await readJson(path.join(PUBLIC, 'dataset.json'));
  const originals = await Promise.all(
    config.countries.map((country) => readFile(path.join(PUBLIC, country.source), 'utf8')),
  );
  const sources = await readDataset();
  for (const [index, source] of sources.entries()) {
    assert.ok(originals[index].includes('<mediaContent>'));
    assert.ok(source.xml.includes('<mediaContent>'));
    assert.equal(source.xml, originals[index]);
    assert.equal(source.originalXml, originals[index]);
    const { media } = parseIsm(source.xml, source.origin);
    assert.equal(media.length, 1);
    assert.equal(
      await readFile(path.join(PUBLIC, config.countries[index].source), 'utf8'),
      originals[index],
    );
  }
});

test('profiles have isolated generated directories', () => {
  assert.equal(datasetOutputDirectory(), path.join(PUBLIC, 'generated'));
  assert.equal(
    datasetOutputDirectory('internal'),
    fileURLToPath(new URL('../../ism/internal/generated', import.meta.url)),
  );
  assert.throws(() => datasetOutputDirectory('unknown'), { code: 'DATASET_INVALID' });
});

test('configured names remain available when diagnostics reports an unsupported mask', async () => {
  await withDirectory(async (directory) => {
    const invalidXml = SYNTHETIC_XML.replace('<patientSearch>', '<unsupported>').replace(
      '</patientSearch>',
      '</unsupported>',
    );
    await writeFile(path.join(directory, 'zz.xml'), invalidXml);
    const configPath = await writeConfig(directory);
    const outDir = path.join(directory, 'output');
    const manifest = await generateDataset({
      profile: 'internal',
      configPath,
      outDir,
      diagnostics: true,
    });
    assert.equal(manifest.countries[0].status, 'unavailable');
    assert.equal(manifest.countries[0].error.code, 'PROFILE_MISMATCH');
    assert.deepEqual(await readJson(path.join(outDir, 'countries.json')), [
      { code: 'ZZ', name: 'Synthetic internal country' },
    ]);
    const failure = await readJson(path.join(outDir, 'ZZ.json'));
    assert.equal(failure.patientSearch, undefined);
  });
});

test('switching profiles removes all tracked artifacts but preserves unrelated files', async () => {
  await withDirectory(async (directory) => {
    const outDir = path.join(directory, 'output');
    await writeFile(path.join(directory, 'zz.xml'), SYNTHETIC_XML);
    const configPath = await writeConfig(directory);
    await generateDataset({ outDir });
    await writeFile(path.join(outDir, 'keep.txt'), 'unrelated');
    const internal = await generateDataset({ profile: 'internal', configPath, outDir });
    assert.deepEqual((await readdir(outDir)).sort(), [
      'ZZ.json',
      'countries.json',
      'keep.txt',
      'manifest.json',
    ]);
    assert.deepEqual(await readJson(path.join(outDir, 'countries.json')), [
      { code: 'ZZ', name: 'Synthetic internal country' },
    ]);
    assert.equal(internal.countries[0].status, 'available');
    const publicDataset = await generateDataset({ outDir });
    assert.deepEqual(
      (await readdir(outDir)).sort(),
      [...publicDataset.files.map((file) => file.path), 'keep.txt', 'manifest.json'].sort(),
    );
    assert.equal(await readFile(path.join(outDir, 'keep.txt'), 'utf8'), 'unrelated');
  });
});

for (const [description, countries, code] of [
  ['empty country list', [], 'DATASET_INVALID'],
  ['duplicate codes', [SYNTHETIC_INTERNAL, SYNTHETIC_INTERNAL], 'DATASET_INVALID'],
  ['invalid code', [{ ...SYNTHETIC_INTERNAL, code: 'z1' }], 'DATASET_INVALID'],
  ['empty name', [{ ...SYNTHETIC_INTERNAL, name: ' ' }], 'DATASET_INVALID'],
  ['missing source', [{ ...SYNTHETIC_INTERNAL, source: 'missing.xml' }], 'ENOENT'],
  ['missing flag', [{ ...SYNTHETIC_INTERNAL, flag: 'missing.svg' }], 'ENOENT'],
  [
    'external help overlay',
    [{ ...SYNTHETIC_INTERNAL, help: { file: 'missing.png', description: 'Help' } }],
    'DATASET_INVALID',
  ],
  ['escaping path', [{ ...SYNTHETIC_INTERNAL, source: '../outside.xml' }], 'DATASET_INVALID'],
  [
    'absolute path',
    [{ ...SYNTHETIC_INTERNAL, source: path.resolve('outside.xml') }],
    'DATASET_INVALID',
  ],
  ['mismatched code', [{ ...SYNTHETIC_INTERNAL, code: 'XY' }], 'DATASET_INVALID'],
  ['invalid flag extension', [{ ...SYNTHETIC_INTERNAL, flag: 'zz.xml' }], 'DATASET_INVALID'],
]) {
  test(`rejects ${description} before changing existing output`, async () => {
    await withDirectory(async (directory) => {
      await writeFile(path.join(directory, 'zz.xml'), SYNTHETIC_XML);
      const configPath = await writeConfig(directory, countries);
      const outDir = path.join(directory, 'output');
      const original = await generateDataset({ outDir });
      await assert.rejects(
        generateDataset({ profile: 'internal', configPath, outDir, diagnostics: true }),
        { code },
      );
      assert.deepEqual(await readJson(path.join(outDir, 'manifest.json')), original);
      assert.deepEqual(
        (await readdir(outDir)).sort(),
        [...original.files.map((file) => file.path), 'manifest.json'].sort(),
      );
    });
  });
}

test('missing or malformed config and unknown profiles fail without fallback', async () => {
  await withDirectory(async (directory) => {
    const configPath = path.join(directory, 'missing.json');
    await assert.rejects(readDataset({ profile: 'internal', configPath }), { code: 'ENOENT' });
    await writeFile(configPath, '{broken');
    await assert.rejects(readDataset({ configPath }), { code: 'DATASET_INVALID' });
    await writeFile(configPath, '{}');
    await assert.rejects(readDataset({ configPath }), { code: 'DATASET_INVALID' });
    await assert.rejects(readDataset({ profile: 'unknown' }), { code: 'DATASET_INVALID' });
  });
});

test('CLI defaults to public and keeps explicit source mode compatible', async () => {
  await withDirectory(async (directory) => {
    const outDir = path.join(directory, 'output');
    await execute(process.execPath, [CLI, '--out', outDir]);
    assert.deepEqual(
      (await readJson(path.join(outDir, 'countries.json'))).map((country) => country.code),
      ['XA', 'XB', 'XC'],
    );
    const source = path.join(directory, 'zz.xml');
    await writeFile(source, SYNTHETIC_XML);
    await execute(process.execPath, [CLI, '--source', source, '--out', outDir]);
    assert.deepEqual(await readJson(path.join(outDir, 'countries.json')), [
      { code: 'ZZ', name: 'ZZ' },
    ]);
    const configPath = await writeConfig(directory);
    await execute(process.execPath, [
      CLI,
      '--profile',
      'internal',
      '--config',
      configPath,
      '--out',
      outDir,
    ]);
    assert.deepEqual(await readJson(path.join(outDir, 'countries.json')), [
      { code: 'ZZ', name: 'Synthetic internal country' },
    ]);
    await assert.rejects(
      execute(process.execPath, [CLI, '--source', source, '--profile', 'public', '--out', outDir]),
      (error) => error.stderr.includes('USAGE'),
    );
  });
});
