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

import { DOMParser } from '@xmldom/xmldom';
import { IsmGenerationError } from './errors.mjs';

export const ISM_NAMESPACE = 'http://ec.europa.eu/sante/ehncp/ism';
export const MODEL_VERSION = 1;

export function sourceCountryCode(xml, origin) {
  const document = parseXml(xml, origin);
  const country = single(
    Array.from(document.getElementsByTagNameNS(ISM_NAMESPACE, 'country')),
    'country',
    origin,
  );
  const code = requiredAttribute(country, 'code', origin);
  if (!/^[A-Z]{2}$/.test(code)) {
    throw new IsmGenerationError('PROFILE_MISMATCH', `${origin}: ungültiger Landcode.`);
  }
  return code;
}

const MEDIA_TYPES = {
  jpg: { mediaType: 'image/jpeg', signature: [0xff, 0xd8, 0xff] },
  jpeg: { mediaType: 'image/jpeg', signature: [0xff, 0xd8, 0xff] },
  png: { mediaType: 'image/png', signature: [0x89, 0x50, 0x4e, 0x47] },
};
const BASE64 = /^[A-Za-z0-9+/]+={0,2}$/;

/**
 * Wandelt die patientSearch-Angaben einer ISM in ein Anzeigemodell um.
 * Unterstützt wird bewusst nur das geprüfte Profil; alles andere bricht ab,
 * damit keine Suchregel stillschweigend verloren geht.
 *
 * @returns {{ model: object, media: { file: string, content: Buffer }[] }}
 */
export function parseIsm(xml, origin) {
  const country = findCountry(parseXml(xml, origin), origin);
  const countryCode = requiredAttribute(country, 'code', origin);
  const patientSearch = single(children(country, 'patientSearch'), 'patientSearch', origin);
  rejectUnsupportedChildren(patientSearch, ['identifier', 'media'], 'patientSearch', origin);

  const media = children(patientSearch, 'media').map((node) =>
    parseMedia(node, countryCode, origin),
  );
  const fields = [];
  const choiceGroups = [];
  for (const identifier of children(patientSearch, 'identifier')) {
    const parsed = parseIdentifier(identifier, origin);
    if (parsed.alternatives) {
      choiceGroups.push({
        alternatives: parsed.alternatives.map(({ display, fields: alternativeFields }) => {
          const fieldIndexes = alternativeFields.map((_, index) => fields.length + index);
          fields.push(...alternativeFields);
          return { display, fieldIndexes };
        }),
      });
    } else {
      fields.push(...parsed.fields);
    }
  }
  const model = {
    modelVersion: MODEL_VERSION,
    country: { code: countryCode, label: requiredAttribute(country, 'label', origin) },
    patientSearch: {
      friendlyName: optionalAttribute(patientSearch, 'friendlyName'),
      scope: optionalAttribute(patientSearch, 'scope'),
      fields,
      ...(choiceGroups.length ? { choiceGroups } : {}),
      helpMedia: media.map(({ description, file, mediaType, name }) => ({
        description,
        file,
        mediaType,
        name,
      })),
    },
  };
  if (model.patientSearch.fields.length === 0) {
    throw new IsmGenerationError(
      'NO_SEARCH_FIELDS',
      `${origin}: patientSearch enthält kein Eingabefeld.`,
    );
  }
  return { model, media: media.map(({ content, file }) => ({ content, file })) };
}

export function parseXml(xml, origin) {
  let failure = null;
  const parser = new DOMParser({
    onError: (level, message) => {
      if (level !== 'warning') {
        failure ??= message;
      }
    },
  });
  try {
    const document = parser.parseFromString(xml, 'text/xml');
    if (!failure) {
      return document;
    }
  } catch (error) {
    // xmldom bricht bei fatalen Fehlern selbst ab und wirft einen ParseError.
    failure ??= error.message;
  }
  throw new IsmGenerationError('XML_INVALID', `${origin}: ${failure}`);
}

function findCountry(document, origin) {
  const roots = Array.from(document.getElementsByTagNameNS(ISM_NAMESPACE, 'searchFields'));
  const root = single(roots, 'searchFields', origin);
  return single(children(root, 'country'), 'country', origin);
}

function parseIdentifier(identifier, origin) {
  const type = requiredAttribute(identifier, 'type', origin);
  if (type === 'CHOICE') {
    rejectUnsupportedChildren(identifier, ['ids'], 'identifier', origin);
    const alternatives = children(identifier, 'ids').map((ids) => {
      rejectUnsupportedChildren(ids, ['id'], 'ids', origin);
      return {
        display: requiredAttribute(ids, 'display', origin),
        fields: parseFields(ids, origin),
      };
    });
    if (alternatives.length === 0) {
      throw new IsmGenerationError(
        'NO_SEARCH_FIELDS',
        `${origin}: CHOICE enthält keine Alternative.`,
      );
    }
    return { alternatives };
  }
  if (type !== 'NORMAL') {
    throw new IsmGenerationError(
      'UNSUPPORTED_IDENTIFIER_TYPE',
      `${origin}: identifier type="${type}" wird nicht unterstützt.`,
    );
  }
  rejectUnsupportedChildren(identifier, ['id'], 'identifier', origin);
  return { fields: parseFields(identifier, origin) };
}

function parseFields(parent, origin) {
  const fields = children(parent, 'id').map((id) => parseField(id, origin));
  if (fields.length === 0) {
    throw new IsmGenerationError(
      'NO_SEARCH_FIELDS',
      `${origin}: ${parent.localName} enthält kein Eingabefeld.`,
    );
  }
  return fields;
}

function parseField(id, origin) {
  const label = requiredAttribute(id, 'label', origin);
  return {
    domain: requiredAttribute(id, 'domain', origin),
    label,
    description: requiredAttribute(id, 'contextualDescription', origin),
    originalDescription: optionalAttribute(id, 'originalContextualDescription'),
    mandatory: optionalAttribute(id, 'mandatory') === 'true',
    pattern: parsePattern(optionalAttribute(id, 'format'), label, origin),
  };
}

function parsePattern(format, label, origin) {
  if (!format) {
    return null;
  }
  try {
    // HTML-pattern wird als Regex mit v-Flag ausgewertet; dieselbe Prüfung gilt hier.
    new RegExp(`^(?:${format})$`, 'v');
  } catch (error) {
    throw new IsmGenerationError(
      'PATTERN_NOT_PORTABLE',
      `${origin}: format von ${label} ist kein gültiges Browser-Muster (${error.message}).`,
    );
  }
  return format;
}

function parseMedia(media, countryCode, origin) {
  const name = requiredAttribute(media, 'mediaName', origin);
  const extension = requiredAttribute(media, 'fileExtension', origin).toLowerCase();
  const declaredType = MEDIA_TYPES[extension];
  if (!declaredType) {
    throw new IsmGenerationError(
      'UNSUPPORTED_MEDIA_TYPE',
      `${origin}: Dateiendung ${extension} wird nicht unterstützt.`,
    );
  }
  const content = decodeMedia(
    single(children(media, 'mediaContent'), 'mediaContent', origin),
    origin,
  );
  const actual = Object.entries(MEDIA_TYPES).find(([, type]) =>
    type.signature.every((byte, index) => content[index] === byte),
  );
  if (!actual) {
    throw new IsmGenerationError('MEDIA_INVALID', `${origin}: unbekannter Bildinhalt.`);
  }
  const [actualExtension, type] = actual;
  if (type.mediaType !== declaredType.mediaType) {
    console.warn(
      `MEDIA_TYPE_MISMATCH: ${origin}: ${name} deklariert ${declaredType.mediaType}, Inhalt ist ${type.mediaType}; Ausgabe verwendet den erkannten Typ.`,
    );
  }
  const safeName = name.replace(/[^A-Za-z0-9_-]/g, '-');
  return {
    name,
    description: optionalAttribute(media, 'description'),
    mediaType: type.mediaType,
    file: `${countryCode}-${safeName}.${actualExtension}`,
    content,
  };
}

function decodeMedia(node, origin) {
  const text = (node.textContent ?? '').replace(/\s+/g, '');
  if (!BASE64.test(text) || text.length % 4 !== 0) {
    throw new IsmGenerationError(
      'MEDIA_INVALID',
      `${origin}: mediaContent ist kein gültiges Base64.`,
    );
  }
  const content = Buffer.from(text, 'base64');
  return content;
}

function children(parent, localName) {
  return Array.from(parent.childNodes).filter(
    (node) =>
      node.nodeType === 1 && node.namespaceURI === ISM_NAMESPACE && node.localName === localName,
  );
}

function rejectUnsupportedChildren(parent, allowed, parentName, origin) {
  const unsupported = Array.from(parent.childNodes).find(
    (node) =>
      node.nodeType === 1 &&
      !(node.namespaceURI === ISM_NAMESPACE && allowed.includes(node.localName)),
  );
  if (unsupported) {
    throw new IsmGenerationError(
      'UNSUPPORTED_ELEMENT',
      `${origin}: ${parentName}/${unsupported.localName} wird nicht unterstützt.`,
    );
  }
}

function single(nodes, name, origin) {
  if (nodes.length !== 1) {
    throw new IsmGenerationError(
      'PROFILE_MISMATCH',
      `${origin}: erwartet genau ein ${name}, gefunden ${nodes.length}.`,
    );
  }
  return nodes[0];
}

function requiredAttribute(node, name, origin) {
  const value = node.getAttribute(name);
  if (!value) {
    throw new IsmGenerationError(
      'ATTRIBUTE_MISSING',
      `${origin}: ${node.localName}@${name} fehlt.`,
    );
  }
  return value;
}

function optionalAttribute(node, name) {
  return node.getAttribute(name) || null;
}
