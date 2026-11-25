# ISM datasets

Two sibling datasets keep public examples separate from internal originals.

| Directory            | Contents                                                                      |
| -------------------- | ----------------------------------------------------------------------------- |
| `public/sources`     | Fictional XA, XB and XC search masks with inline base64 PNG help              |
| `public/flags`       | Original synthetic flag SVG and PNG artwork                                   |
| `public/artwork`     | Original synthetic help PNG and SVG artwork                                   |
| `public/generated`   | Generated models, extracted help images, copied flag SVGs and country index   |
| `internal/sources`   | All original real ISM XML files, preserved unchanged                          |
| `internal/flags`     | Original reviewed real country SVG flags with upstream README and MIT license |
| `internal/generated` | Generated real country models, help images and country index                  |

Internal originals remain versioned in GitLab. GitHub export must exclude the
entire `internal` directory, including generated exports, and the real-country
examples in `specs/ism/examples/`. The public profile never reads internal
sources.

## Commands

Run from `frontend`:

```powershell
npm run ism:generate
npm start
npm run build
```

These commands select `public`. Internal development is explicit:

```powershell
npm run ism:generate:internal
npm run start:internal
npm run build:internal
```

Internal start and build use Angular configuration `internal`. Angular assets
configuration exposes only the selected dataset's `generated` directory at
`/ism`. Neither source XML nor original artwork is published as application
assets. Profile generation does not overwrite the other profile's exports.

## Generator configuration

`public/dataset.json` contains a `countries` array. Each entry requires `code`,
`name` and a relative `source` path. An optional `flag` path identifies an SVG.
All files must resolve within the config directory, including symlink targets.
Duplicate codes, missing files and mismatched XML country codes fail explicitly.
Help belongs in the XML, not a configuration overlay.

The internal profile uses a curated mapping in `tools/ism/datasets.mjs`.
It retains all 26 existing German country labels. Additional original files
remain preserved but are not automatically added to the selectable country list.
Missing internal files fail generation without falling back to public examples.
Internal flags are moved unchanged from the existing `frontend/public/flags`
assets, originating from the MIT licensed flag-icons project:
<https://github.com/lipis/flag-icons>. Upstream attribution and the complete
license remain alongside the SVG files.
The curated internal country index omits `flag` so real countries retain emoji
mode. Internal Angular configuration separately exposes `internal/flags` at
`/flags` for the existing lowercase country-code image fallback.

An explicit configuration can replace either dataset mapping:

```powershell
node tools\ism\generate-ism.mjs --profile public --config ism\public\dataset.json
node tools\ism\generate-ism.mjs --profile internal --config path\to\dataset.json --out path\to\generated
```

The original `--source <file-or-directory> --out <directory>` interface remains
available. It cannot be combined with `--profile` or `--config`.

## Generated integration contract

Each selected `generated` directory contains `countries.json` as an array:

```json
[{ "code": "XA", "name": "Aveloria", "flag": "ism/XA-flag.svg" }]
```

`flag` is optional. URLs are relative to the application's browser base.
Models are `<code>.json`. Help image filenames are specified by each model's
`patientSearch.helpMedia[].file` and resolved relative to `/ism`.
Public help images are `<code>-identification-help.png`.

`manifest.json` tracks all generated outputs, including countries and flags.
Regeneration removes previously tracked files in its output directory while
preserving unrelated files. XML bytes are not modified during generation.
Diagnostic mode writes explicit unavailable models for unsupported source masks.

## Public examples and schema

The independently authored examples describe no real countries or people.
Identifier domains use the reserved `.example` domain.

| Source                  | Country  | Search structure                                          |
| ----------------------- | -------- | --------------------------------------------------------- |
| `public/sources/xa.xml` | Aveloria | Two independent CHOICE groups, each with two alternatives |
| `public/sources/xb.xml` | Belvaria | Three fields, two required and one optional               |
| `public/sources/xc.xml` | Caldoria | One required field                                        |

Each source XML embeds the matching PNG from `public/artwork` as base64.
The PNG and SVG artwork files remain available separately for review and reuse.

`public/demo-ism.xsd` is derived from
[`ehdsi-ism-2023.xsd`](../../specs/ism/schema/ehdsi-ism-2023.xsd).
Only its country code enumeration differs, allowing XA, XB and XC.
A comment at the top of the file states its source, license and modification.
The parser checks its supported rendering profile. XSD validation is separate.

Both schemas are licensed under the Apache License, Version 2.0. The
[schema README](../../specs/ism/schema/README.md) documents the pinned upstream
commit and checksum. Attribution notices are listed in [NOTICE](../../NOTICE).
Artwork generation terms remain part of OSPO review.
