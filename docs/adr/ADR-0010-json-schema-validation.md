# ADR-0010: Use `jsonschema` for OpenAPI 3.1 schema validation

## Status

Accepted

## Context

The tool must validate OpenAPI 3.1 Schema Objects, the document-level
`jsonSchemaDialect`, and schema-local `$schema` overrides. Implementing JSON
Schema metaschema validation manually would be incomplete and error-prone.
The tool must not fetch arbitrary dialects from the network, because
specifications are untrusted input.

## Decision

Use the maintained Python `jsonschema` package for local metaschema checks.
V1 supports an explicit local mapping of:

- OpenAPI 3.1 base dialect
- JSON Schema Draft 2020-12
- JSON Schema Draft 2019-09
- JSON Schema Draft 7

The OpenAPI 3.1 base dialect is checked with Draft 2020-12 semantics, while
retaining its OpenAPI URI as the effective dialect identifier. The tool first
validates that each declared dialect is an absolute URI. Any URI not in the
local mapping fails with `OPENAPI_JSON_SCHEMA_DIALECT_UNSUPPORTED`; it is never
fetched remotely.

## Consequences

Schema validation is standards-based without network access. Users of custom
JSON Schema vocabularies receive an explicit diagnostic until support is added,
rather than having declarations silently ignored or resolved remotely.
