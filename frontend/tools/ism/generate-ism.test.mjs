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
import { mkdtemp, readFile, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { generateIsm } from './generate-ism.mjs';
import { parseIsm } from './parse-ism.mjs';
import { readFileSource } from './sources.mjs';

const JPEG_BASE64 = Buffer.from([0xff, 0xd8, 0xff, 0xe0, 0x00]).toString('base64');

function ism({ patientSearch, country = 'code="XA" label="label.ism.addressCountry"' } = {}) {
  return `<Extension><s:searchFields xmlns="http://ec.europa.eu/sante/ehncp/ism" xmlns:s="http://ec.europa.eu/sante/ehncp/ism">
    <country ${country}>${
      patientSearch ??
      `<patientSearch scope="ALL">
        <identifier type="NORMAL">
          <id contextualDescription="Example identifier" domain="https://example.test/id"
              format="^[A-Z]{2}$" label="label.ism.id" mandatory="true"
              originalContextualDescription="Synthetic identifier"/>
        </identifier>
        <media description="Example card" fileExtension="JPG" mediaName="XA example">
          <mediaContent>${JPEG_BASE64}</mediaContent>
        </media>
      </patientSearch>`
    }</country>
  </s:searchFields></Extension>`;
}

const rejects = (xml, code) =>
  assert.throws(
    () => parseIsm(xml, 'test.xml'),
    (error) => error.code === code,
  );

for (const [code, fieldCount, choiceCount] of [
  ['XA', 6, 2],
  ['XB', 3, 0],
  ['XC', 1, 0],
]) {
  test(`parses synthetic ${code} example with its intended search structure`, async () => {
    const [source] = await readFileSource(
      fileURLToPath(new URL(`../../ism/public/sources/${code.toLowerCase()}.xml`, import.meta.url)),
    );
    const { model, media } = parseIsm(source.xml, source.origin);
    assert.equal(model.country.code, code);
    assert.equal(model.patientSearch.fields.length, fieldCount);
    assert.equal(model.patientSearch.choiceGroups?.length ?? 0, choiceCount);
    assert.equal(media.length, 1);
    assert.equal(model.patientSearch.helpMedia[0].mediaType, 'image/png');
    for (const field of model.patientSearch.fields) {
      assert.ok(new URL(field.domain).hostname.endsWith('.example'));
    }
    for (const group of model.patientSearch.choiceGroups ?? []) {
      assert.deepEqual(
        group.alternatives.map((alternative) => alternative.fieldIndexes.length),
        [1, 2],
      );
    }
  });
}

test('maps patient search fields, pattern, mandatory flag and help media', () => {
  const { model, media } = parseIsm(ism(), 'test.xml');

  assert.deepEqual(model.patientSearch.fields, [
    {
      domain: 'https://example.test/id',
      label: 'label.ism.id',
      description: 'Example identifier',
      originalDescription: 'Synthetic identifier',
      mandatory: true,
      pattern: '^[A-Z]{2}$',
    },
  ]);
  assert.equal(model.patientSearch.helpMedia[0].file, 'XA-XA-example.jpg');
  assert.equal(model.patientSearch.helpMedia[0].mediaType, 'image/jpeg');
  assert.equal(media[0].content.length, 5);
});

test('keeps a missing format as no pattern instead of guessing one', () => {
  const xml = ism({
    patientSearch: `<patientSearch><identifier type="NORMAL">
      <id contextualDescription="x" domain="1" label="label.ism.id" format=""/></identifier></patientSearch>`,
  });

  assert.equal(parseIsm(xml, 'test.xml').model.patientSearch.fields[0].pattern, null);
});

test('ignores documentSearch because it is not part of the patient search', () => {
  const xml = ism().replace('</country>', '<documentSearch scope="EP"/></country>');

  assert.equal(parseIsm(xml, 'test.xml').model.patientSearch.fields.length, 1);
});

test('rejects unsupported profile elements and identifier types', () => {
  rejectsPatientSearch('<birthDate label="label.ism.birthDate"/>', 'UNSUPPORTED_ELEMENT');
  rejectsPatientSearch(
    '<identifier type="OTHER"><id contextualDescription="x" domain="1" label="l"/></identifier>',
    'UNSUPPORTED_IDENTIFIER_TYPE',
  );
});

for (const sizes of [
  [2, 1],
  [1, 4],
]) {
  test(`preserves CHOICE alternatives with field counts ${sizes.join(', ')}`, () => {
    const displays = ['Synthetic first alternative', 'Synthetic second alternative'];
    const alternatives = sizes.map(
      (size, alternative) =>
        `<ids display="${displays[alternative]}">${Array.from(
          { length: size },
          (_, index) =>
            `<id domain="https://choice.example/${alternative}/${index}" label="label.ism.id"
            contextualDescription="Synthetic field ${index}" mandatory="true" format="[0-9]+"/>`,
        ).join('')}</ids>`,
    );
    const { model } = parseIsm(
      ism({
        patientSearch: `<patientSearch><identifier type="CHOICE">${alternatives.join('')}</identifier></patientSearch>`,
      }),
      'choice.xml',
    );
    const [group] = model.patientSearch.choiceGroups;
    assert.deepEqual(
      group.alternatives.map((alternative) => alternative.display),
      displays,
    );
    assert.deepEqual(
      group.alternatives.map((alternative) => alternative.fieldIndexes.length),
      sizes,
    );
    assert.deepEqual(
      group.alternatives.flatMap((alternative) => alternative.fieldIndexes),
      model.patientSearch.fields.map((_, index) => index),
    );
    assert.ok(model.patientSearch.fields.every((field) => field.mandatory && field.pattern));
  });
}

test('rejects malformed CHOICE alternatives instead of losing fields', () => {
  rejectsPatientSearch('<identifier type="CHOICE"/>', 'NO_SEARCH_FIELDS');
  rejectsPatientSearch(
    '<identifier type="CHOICE"><ids display="x"/></identifier>',
    'NO_SEARCH_FIELDS',
  );
  rejectsPatientSearch(
    '<identifier type="CHOICE"><id domain="1" label="l" contextualDescription="x"/></identifier>',
    'UNSUPPORTED_ELEMENT',
  );
  rejectsPatientSearch(
    '<identifier type="CHOICE"><ids><id domain="1" label="l" contextualDescription="x"/></ids></identifier>',
    'ATTRIBUTE_MISSING',
  );
});

test('keeps multiple CHOICE groups independent and NORMAL fields unconditional', () => {
  const choice = (display) => `<identifier type="CHOICE"><ids display="${display}">
    <id domain="1" label="l" contextualDescription="${display}"/></ids></identifier>`;
  const { model } = parseIsm(
    ism({
      patientSearch: `<patientSearch>${choice('First')}
      <identifier type="NORMAL"><id domain="1" label="l" contextualDescription="Always"/></identifier>
      ${choice('Second')}</patientSearch>`,
    }),
    'test.xml',
  );
  assert.deepEqual(
    model.patientSearch.choiceGroups.map((group) => group.alternatives[0].fieldIndexes),
    [[0], [2]],
  );
  assert.deepEqual(
    model.patientSearch.fields.map((field) => field.description),
    ['First', 'Always', 'Second'],
  );
});

function rejectsPatientSearch(content, code) {
  const body = content.startsWith('<identifier')
    ? content
    : `<identifier type="NORMAL"><id contextualDescription="x" domain="1" label="l"/></identifier>${content}`;
  rejects(ism({ patientSearch: `<patientSearch>${body}</patientSearch>` }), code);
}

test('rejects a format that browsers cannot use as pattern', () => {
  rejects(
    ism({
      patientSearch: `<patientSearch><identifier type="NORMAL">
        <id contextualDescription="x" domain="1" label="l" format="[0-9"/></identifier></patientSearch>`,
    }),
    'PATTERN_NOT_PORTABLE',
  );
});

test('rejects missing required attributes and empty search masks', () => {
  rejects(ism({ country: 'label="label.ism.addressCountry"' }), 'ATTRIBUTE_MISSING');
  rejects(ism({ patientSearch: '<patientSearch/>' }), 'NO_SEARCH_FIELDS');
});

test('rejects media with invalid base64, wrong signature or unsupported type', () => {
  const media = (extension, content) =>
    ism({
      patientSearch: `<patientSearch><identifier type="NORMAL">
        <id contextualDescription="x" domain="1" label="l"/></identifier>
        <media fileExtension="${extension}" mediaName="m"><mediaContent>${content}</mediaContent></media></patientSearch>`,
    });

  rejects(media('JPG', 'not base64!'), 'MEDIA_INVALID');
  const corrected = parseIsm(media('PNG', JPEG_BASE64), 'test.xml');
  assert.equal(corrected.model.patientSearch.helpMedia[0].mediaType, 'image/jpeg');
  assert.ok(corrected.media[0].file.endsWith('.jpg'));
  rejects(media('GIF', JPEG_BASE64), 'UNSUPPORTED_MEDIA_TYPE');
});

test('rejects malformed XML and documents without exactly one search mask', () => {
  rejects('<Extension><unclosed></Extension>', 'XML_INVALID');
  rejects('<Extension/>', 'PROFILE_MISMATCH');
});

test('writes deterministic output and replaces files of the previous run', async () => {
  const outDir = await mkdtemp(path.join(tmpdir(), 'ism-'));
  try {
    const sources = [{ origin: 'xa.xml', xml: ism() }];
    const first = await generateIsm({ sources, outDir });
    const firstModel = await readFile(path.join(outDir, 'XA.json'), 'utf8');
    const second = await generateIsm({ sources, outDir });

    assert.deepEqual(second, first);
    assert.equal(await readFile(path.join(outDir, 'XA.json'), 'utf8'), firstModel);
    assert.deepEqual((await readdir(outDir)).sort(), [
      'XA-XA-example.jpg',
      'XA.json',
      'countries.json',
      'manifest.json',
    ]);
    assert.match(first.countries[0].source.sha256, /^[0-9a-f]{64}$/);
  } finally {
    await rm(outDir, { recursive: true, force: true });
  }
});

test('writes nothing when one source cannot be processed', async () => {
  const outDir = await mkdtemp(path.join(tmpdir(), 'ism-'));
  try {
    await assert.rejects(
      generateIsm({ sources: [{ origin: 'x.xml', xml: '<Extension/>' }], outDir }),
      { code: 'PROFILE_MISMATCH' },
    );
    assert.deepEqual(await readdir(outDir), []);
  } finally {
    await rm(outDir, { recursive: true, force: true });
  }
});

test('rejects duplicate countries and empty source lists', async () => {
  const outDir = await mkdtemp(path.join(tmpdir(), 'ism-'));
  try {
    const source = { origin: 'xa.xml', xml: ism() };
    await assert.rejects(generateIsm({ sources: [source, source], outDir }), {
      code: 'DUPLICATE_COUNTRY',
    });
    await assert.rejects(generateIsm({ sources: [], outDir }), { code: 'NO_SOURCES' });
  } finally {
    await rm(outDir, { recursive: true, force: true });
  }
});

test('processes a synthetic searchFields fragment with embedded media', () => {
  const xml = ism().replace('<Extension>', '').replace('</Extension>', '');
  const { model, media } = parseIsm(xml, 'fragment.xml');

  assert.equal(model.country.code, 'XA');
  assert.equal(model.patientSearch.fields.length, 1);
  assert.equal(model.patientSearch.fields[0].pattern, '^[A-Z]{2}$');
  assert.equal(model.patientSearch.fields[0].mandatory, true);
  assert.equal(media.length, 1);
  assert.equal(media[0].content.toString('base64'), JPEG_BASE64);
});

test('maps a searchFields fragment and an SMP envelope to the same model and media', () => {
  const xml = ism().replace('<Extension>', '').replace('</Extension>', '');
  const wrapped = `<SignedServiceMetadata xmlns="http://docs.oasis-open.org/bdxr/ns/SMP/2016/05"><Extension>${xml}</Extension></SignedServiceMetadata>`;
  assert.deepEqual(parseIsm(xml, 'fragment.xml'), parseIsm(wrapped, 'fragment.xml'));
});

test('preserves field order and distinct patterns in a synthetic multi-field mask', () => {
  const patterns = ['[A-Z]{2}[0-9]{6}', '[0-9]{5}', '\\d{9}'];
  const { model } = parseIsm(
    ism({
      patientSearch: `<patientSearch><identifier type="NORMAL">${patterns
        .map(
          (pattern, index) => `<id domain="https://multi.example/${index}" label="label.ism.id"
            contextualDescription="Synthetic field ${index}" mandatory="true" format="${pattern}"/>`,
        )
        .join('')}</identifier></patientSearch>`,
    }),
    'multi.xml',
  );
  assert.deepEqual(
    model.patientSearch.fields.map((field) => field.description),
    patterns.map((_, index) => `Synthetic field ${index}`),
  );
  assert.deepEqual(
    model.patientSearch.fields.map((field) => field.pattern),
    patterns,
  );
  assert.ok(model.patientSearch.fields.every((field) => field.mandatory));
});

test('preserves separate fields sharing a domain in source order', () => {
  const { model } = parseIsm(
    ism({
      patientSearch: `<patientSearch><identifier type="NORMAL">
      <id domain="1" label="l" contextualDescription="First" format="[0-9]+" mandatory="true"/>
      <id domain="1" label="l" contextualDescription="Second" format="[A-Z]+" mandatory="false"/>
    </identifier></patientSearch>`,
    }),
    'test.xml',
  );
  assert.deepEqual(
    model.patientSearch.fields.map((field) => field.domain),
    ['1', '1'],
  );
  assert.deepEqual(
    model.patientSearch.fields.map((field) => field.description),
    ['First', 'Second'],
  );
  assert.deepEqual(
    model.patientSearch.fields.map((field) => field.mandatory),
    [true, false],
  );
});

test('diagnostic mode preserves malformed synthetic profiles as explicit failures', async () => {
  const outDir = await mkdtemp(path.join(tmpdir(), 'ism-'));
  try {
    const sources = ['XA', 'XB'].map((code) => ({
      origin: `${code.toLowerCase()}.xml`,
      xml: ism({ country: `code="${code}" label="label.ism.addressCountry"` })
        .replace('s:searchFields', 's:unsupported')
        .replace('</s:searchFields>', '</s:unsupported>'),
    }));
    sources.push({
      origin: 'xc.xml',
      xml: ism({ country: 'code="XC" label="label.ism.addressCountry"' }),
    });
    const manifest = await generateIsm({ sources, outDir, diagnostics: true });
    assert.deepEqual(
      manifest.countries.map(({ code, status }) => ({ code, status })),
      [
        { code: 'XA', status: 'unavailable' },
        { code: 'XB', status: 'unavailable' },
        { code: 'XC', status: 'available' },
      ],
    );
    const failure = JSON.parse(await readFile(path.join(outDir, 'XA.json'), 'utf8'));
    assert.equal(failure.generationError.code, 'PROFILE_MISMATCH');
    assert.equal(failure.patientSearch, undefined);
  } finally {
    await rm(outDir, { recursive: true, force: true });
  }
});

test('diagnostic mode collapses identical country sources but refuses conflicting ones', async () => {
  const outDir = await mkdtemp(path.join(tmpdir(), 'ism-'));
  try {
    const source = { origin: 'xa.xml', xml: ism() };
    const manifest = await generateIsm({
      sources: [source, { ...source, origin: 'duplicate.xml' }],
      outDir,
      diagnostics: true,
    });
    assert.equal(manifest.countries.length, 1);
    await assert.rejects(
      generateIsm({
        sources: [
          source,
          {
            origin: 'changed.xml',
            xml: ism().replace(
              'contextualDescription="Example identifier"',
              'contextualDescription="Changed example identifier"',
            ),
          },
        ],
        outDir,
        diagnostics: true,
      }),
      { code: 'DUPLICATE_COUNTRY' },
    );
  } finally {
    await rm(outDir, { recursive: true, force: true });
  }
});
