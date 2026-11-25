# OpenAPI/Arazzo Mocking Test Tool

## Current repository state

The repository contains existing Node.js proof-of-concept scripts for scenario
generation and specification collection. The primary mocking/test tool uses
Python, with PyYAML for controlled YAML loading and the standard library for
the CLI and initial tests.

## Proposed architecture

```text
CLI
  -> configuration and diagnostics
  -> OpenAPI loader/model
  -> Arazzo loader/model
  -> cross validation
  -> workflow runner and HTTP execution
  -> contract assertions, mocking, reporting
```

The implementation stays in `tools/`, with project-owned interfaces around
standards libraries. External YAML/JSON representations will not leak into
runtime models.

## Domain concepts and boundaries

- `tools/openapi_arazzo_tool/config.py`: tool configuration and secure defaults.
- `tools/openapi_arazzo_tool/errors.py`: stable diagnostic codes and exit codes.
- `tools/openapi_arazzo_tool/cli.py`: primary Python CLI boundary.
- OpenAPI model/validation: OpenAPI 3.1.x only.
- Arazzo model/validation: supported V1 feature matrix only.
- Runner, HTTP, assertions, mocking, and reporting remain separate modules.

## Dependency choices

Milestone 0 uses PyYAML and Python's built-in `unittest`. Milestone 1 adds
the maintained `jsonschema` library for local JSON Schema metaschema checks;
ADR-0010 records the explicit, network-free dialect mapping. Milestone 6 will
use `httpx` for controlled HTTP execution because it provides explicit
timeouts, redirect control, and test transports. Target allowlisting, SSRF
protection, redirect revalidation, and response limits remain project-owned
security controls.

## Testing strategy

Use Node's built-in test runner for unit tests, fixture tests for document
validation, integration tests for OpenAPI/Arazzo combinations, and a small
deterministic end-to-end example. Security controls receive dedicated
negative tests.

## Milestones

0. Foundation: CLI, configuration, diagnostics, tests, Docker skeleton.
1. OpenAPI 3.1 loading and validation.
2. Arazzo loading and V1 support-matrix validation.
3. OpenAPI/Arazzo cross validation.
4. Runtime expression parser and evaluator.
5. OpenAPI HTTP request construction.
6. Secure target resolution and HTTP execution.
7. Direct Arazzo workflow runner.
8. OpenAPI request/response contract assertions.
9. Stateless deterministic mock server.
10. Test scenarios and run isolation.
11. Authentication and secret redaction.
12. Console, JSON, JUnit, and optional HTML reporting.
13. Docker and CI integration completion.
14. Exportable mock packages and versioned Python/Docker runtime.

## Milestone 14 acceptance criteria

- A generation command produces a versioned package directory from validated
  OpenAPI inputs. It contains pre-generated routes and deterministic
  responses, all runtime request-validation contract data, the complete
  source OpenAPI/Arazzo definitions for traceability, and a provenance
  manifest. Arazzo is retained for reference; the mock runtime does not
  execute workflows.
- The package is validated before publication. Invalid specifications,
  unsupported package versions, invalid generated responses, and incomplete
  or corrupted packages fail explicitly and do not produce a successful
  release artifact.
- A runtime command starts a mock using only the generated package and
  separate runtime settings such as bind address and port. Runtime request
  validation uses precomputed package contract data; OpenAPI/Arazzo sources
  and generation rules are not re-evaluated.
- The same package can be started directly by Python or included with its
  compatible Python server runtime in an image built for that mock version.
- Safe defaults bind local runs to `127.0.0.1` and a documented default port.
  Port and bind address can be overridden. Container ports are not published
  by default; host/remote access requires explicit bind and port configuration.
- Package and generator use independent semantic versions; neither version is
  inferred from or tied to the other. The manifest identifies input and
  generator versions or hashes. Identical inputs and generator versions
  produce deterministic package content.
- Tests cover package generation, both runtime paths, request validation,
  corrupted/incompatible packages, startup failures, and clean shutdown.

### Milestone 14 implementation status

Package-directory export, independent package/generator versions, integrity
checks, package-based Python startup, and a per-version Dockerfile are
implemented. Export now verifies the complete temporary package before
publication and preserves fractional-millisecond scenario delays.
CLI regression coverage includes exporting mTLS specifications without a
runner-executability check and refusing to overwrite existing releases.
The source archive includes transitive local reference dependencies and
Arazzo OpenAPI source descriptions, with portable reference provenance in
the manifest. Original source bytes are retained as numbered archive copies;
the runtime uses bundled contract data rather than reparsing those copies.
Package regression tests were confirmed successful by the user. Docker
build/runtime acceptance was completed on 2026-10-06 using the example
configuration `tools/mock-package-demo.yaml`: the image runs unprivileged
with a read-only filesystem, without source mounts, and returns 200 for a
valid request, 400 for missing/invalid query parameters, and 404 for an
unknown route. Defaults expose no host ports. Explicit loopback host-port
publication was also verified. SIGTERM now closes the mock server and exits
with code 0 instead of waiting for Docker's forced termination.
The new lifecycle unit tests still require a user-run test pass.

## Milestone 0 acceptance criteria

- `uv run python -m tools.openapi_arazzo_tool.cli --help` lists all V1 command names.
- Known but unfinished commands return `COMMAND_NOT_IMPLEMENTED`, never success.
- Configuration parsing reports `CONFIG_INVALID` and exit code `4`.
- Exit codes `0` through `4` are defined centrally.
- Tests run with `uv run python -m unittest`.
- Docker entrypoint is local and starts with help output.

## Requirement traceability

- [x] Python CLI command surface and explicit exit-code foundation — Milestone 0
- [x] Python configuration loading and error model — Milestone 0
- [x] Python Docker skeleton — Milestone 0
- [x] OpenAPI 3.1 version validation — Milestone 1 (step 1)
- [x] OpenAPI basic document structure validation — Milestone 1 (required
  `info` fields, optional `paths` and `components` object boundaries, path
  item shape, and operation response-object presence; independent errors are
  aggregated as `OPENAPI_STRUCTURE_INVALID`)
- [x] OpenAPI `$ref` resolution — Milestone 1 (step 2: secure local ref
  resolution, canonicalization, root allowlisting; JSON pointer traversal;
  step 3: recursive whole-document resolution via `find_ref_issues`, with a
  visited-set of `(file, fragment)` pairs so legitimate self- and
  cross-file-recursive schemas terminate without being flagged as errors;
  `validate-openapi` now requires `security.allowedRefRoots` explicitly and
  reports `OPENAPI_REF_UNRESOLVED` / `OPENAPI_REF_FORBIDDEN` per Kap. 17 —
  there is no permissive default local-file-access root)
- [x] OpenAPI `operationId` uniqueness — Milestone 1 (global document scope;
  validation is limited to HTTP operation objects in `paths` and reports
  `OPENAPI_OPERATION_ID_DUPLICATE` with both declaration paths)
- [x] OpenAPI parameter definitions — Milestone 1 (inline and reusable
  Parameter Object shape, allowed locations, schema/content exclusivity,
  uniqueness by `(name, in)`, required path parameters, and bidirectional
  path-template matching; unresolved Parameter Object `$ref` values remain
  covered by secure `$ref` validation until dereferencing joins the internal
  model)
- [x] OpenAPI request bodies — Milestone 1 (inline and reusable Request Body
  Object shape, boolean `required`, non-empty `content`, and Media Type Object
  boundaries; content schema compatibility is covered by schema validation)
- [x] OpenAPI response definitions — Milestone 1 (Response Object shape,
  non-empty descriptions, content/header object boundaries, reusable
  component responses, explicit HTTP status codes, status-code ranges, and
  `default`; response selection precedence remains Milestone 8/9 behavior)
- [x] OpenAPI security schemes and requirements — Milestone 1 (all OpenAPI
  Security Scheme Object types, scheme-specific required fields, global and
  operation-level Security Requirement structure, defined-scheme references,
  OR/AND representation, OAuth 2 flow URLs/scopes, and valid scope use;
  runtime credential injection remains Milestone 11)
- [x] OpenAPI examples and multiple examples — Milestone 1 (Example Object
  shape, `value`/`externalValue` exclusivity, `example`/`examples`
  exclusivity, named-example mappings, and component/parameter/header/request/
  response locations; external example values are never fetched during
  validation)
- [x] OpenAPI JSON Schema dialect and schema validation — Milestone 1
  (`jsonSchemaDialect`, schema-local `$schema`, and metaschema validation for
  schemas in OpenAPI component, parameter, request, response, and header
  locations; only an explicit, local dialect allowlist is supported — no
  remote dialect retrieval; see ADR-0010)
- [x] Arazzo 1.1 document loading and version validation — Milestone 2
  (local YAML/JSON loading, mapping-root and syntax validation, explicit
  `ARAZZO_VERSION_UNSUPPORTED` diagnostics for non-1.1.x documents, and
  `validate-arazzo` CLI command)
- [x] Arazzo document structure and source descriptions — Milestone 2
  (required `info`, non-empty source/workflow lists, unique source names, and
  source-description fields; only `openapi` sources are supported, while
  known `asyncapi`/`arazzo` sources explicitly return
  `ARAZZO_FEATURE_UNSUPPORTED`; `x-*` extensions are retained and ignored
  semantically)
- [x] Arazzo workflow and step identities — Milestone 2 (non-empty unique
  `workflowId` and per-workflow `stepId`, non-empty steps, exactly one
  `operationId` or `operationPath` per step, and explicit
  `ARAZZO_FEATURE_UNSUPPORTED` rejection of `operationRef`)
- [x] Arazzo step inputs and request bodies — Milestone 2 (Step Parameter
  Object fields, supported parameter locations, `(name, in)` uniqueness, and
  Request Body `contentType`/`payload` structure; OpenAPI operation and schema
  compatibility remain cross-validation concerns in Milestone 3)
- [x] Arazzo outputs and success criteria — Milestone 2 (workflow and step
  Output Object mappings with Arazzo-conformant names/non-empty expressions plus non-empty
  `successCriteria` condition objects; expression grammar and resolution
  remain Milestone 4)
- [x] Arazzo success/failure actions — Milestone 2 (validated `onSuccess` and
  `onFailure` action arrays, action criteria, V1 `goto`/`retry`/`end` types,
  unique action names, resolved step/workflow goto targets, context-appropriate
  action types, and bounded retry field structure with the Arazzo default single retry;
  static detection of unconditional `goto` cycles; runtime execution remains a
  later increment)
- [x] Arazzo workflow inputs — Milestone 2 (workflow `inputs` are validated
  as local JSON Schema 2020-12 mappings; reference resolution and concrete
  workflow-input values remain Cross Validation and Workflow Runner work)
- [x] Arazzo step-output references — Milestone 2 (structurally resolves
  `$steps.<stepId>.outputs.<name>` references in workflow/step expression
  fields, rejects unknown steps/outputs and per-step forward references; full
  expression grammar and evaluation remain Milestone 4)
- [x] Arazzo unsupported-feature enforcement — Milestone 2 (known
  AsyncAPI `channelPath` and action constructs plus workflow-invocation and
  `operationRef` step constructs explicitly produce
  `ARAZZO_FEATURE_UNSUPPORTED`; `x-*` extensions remain accepted)
- [x] Arazzo reusable-feature enforcement — Milestone 2 (Arazzo
  `components`, reusable action/parameter `$ref` objects, and Selector Objects
  explicitly produce `ARAZZO_FEATURE_UNSUPPORTED`, because they are outside
  the V1 support matrix)
- [x] Arazzo workflow-feature enforcement — Milestone 2 (workflow
  inherited parameters and inherited success/failure actions explicitly produce
  `ARAZZO_FEATURE_UNSUPPORTED`, because V1 supports only directly declared
  step behavior)
- [x] Arazzo dependency validation — Milestone 2 (validates local workflow
  and preceding-step `dependsOn` references, detects self/unknown/duplicate
  and forward dependencies, and preserves deterministic sequential execution)
- [x] Arazzo Step timeout validation — Milestone 2 (validates optional
  non-negative millisecond timeouts before runtime timeout enforcement)
- [x] Arazzo remaining known-field enforcement — Milestone 2 (explicitly
  validate or reject each remaining known non-extension Arazzo field,
  including AsyncAPI-only fields, `$self`, and request-body payload
  replacements, so no semantics are silently ignored)
- [x] Arazzo V1 field allowlist — Milestone 2 (defines and enforces the final
  allowed non-extension fields for supported Arazzo objects; retain `x-*`
  extensions without interpreting them)
- [x] Arazzo parsing and support matrix — Milestone 2
- [x] Cross-validation source resolution — Milestone 3 (securely resolves
  local relative OpenAPI Source Description URLs within
  `security.allowedRefRoots`, blocks remote/absolute/out-of-root sources, and
  validates loaded source documents; `validate-all` executes this first cross
  validation slice)
- [x] Cross-validation operationId resolution — Milestone 3 (resolves
  operation IDs against loaded OpenAPI sources, requires Arazzo source-scoping
  when multiple sources exist, and reports unknown sources/operations)
- [x] Cross-validation operationPath resolution — Milestone 3 (resolves
  source-scoped OpenAPI JSON Pointers to HTTP operations and rejects malformed,
  unknown-source, non-operation, and unresolved paths)
- [x] Cross-validation parameter presence — Milestone 3 (checks Step Parameter
  Object names/locations and required parameter supply against resolved OpenAPI
  operations)
- [x] Cross-validation parameter value schemas — Milestone 3 (validates static
  Step Parameter values against resolved OpenAPI parameter schemas; runtime
  expression values are deferred to Milestone 4)
- [x] Cross-validation request bodies — Milestone 3 (resolves target Request
  Body support, requiredness, media types, and static payload-schema
  compatibility; runtime-expression payloads remain deferred to Milestone 4)
- [x] Cross-validation runtime-expression dependencies — Milestone 3 (verifies
  parsed expression references against workflow inputs/outputs and workflows;
  existing step-output and response-reference validators cover the remaining
  statically available dependencies)
- [x] Cross-validation response references — Milestone 3 (validates statically
  referenced status codes, response headers, and response-body schema paths
  against target OpenAPI responses; full expression evaluation remains
  Milestone 4)
- [x] Security validation boundaries — Milestone 3 (OpenAPI security definitions
  remain structurally validated; static cross validation no longer requires
  runner-supported authentication alternatives, allowing valid mTLS-only
  specifications. Runtime authentication enforcement remains Milestone 11.)
- [x] Cross validation — Milestone 3
- [x] Runtime expressions — Milestone 4 (strict parser and syntax validation
  plus safe evaluation of complete and embedded Arazzo 1.1 expressions
  implemented; evaluation preserves native types, deterministically serializes
  embedded structured values, and resolves JSON Pointers without dynamic code;
  safe `simple` Criterion evaluation supports comparisons, logical operators,
  parentheses, literals, case-insensitive strings, and numeric coercion.
  Criterion context, regex, JSONPath, XPath, and Expression Type Objects
  explicitly produce `ARAZZO_FEATURE_UNSUPPORTED` in V1; runner integration
  belongs to Milestone 7)
- [x] HTTP serialization — Milestone 5 (OpenAPI path/query/header/cookie
  parameter serialization implemented with style/explode defaults,
  simple/label/matrix/form/spaceDelimited/pipeDelimited/deepObject,
  allowReserved, and RFC-compliant percent encoding; request-body serialization
  supports deterministic JSON, form-urlencoded property encoding, deterministic
  multipart text/JSON/binary parts, binary bodies, and text/XML; deterministic
  transport-neutral request assembly combines base paths, encoded query pairs,
  cookies, headers, and bodies while rejecting injection and conflicts)
- [x] Target resolution and secure execution — Milestone 6 (target precedence,
  server-variable resolution, explicit host/port allowlists, resolved-address
  blocking for loopback/private/link-local/metadata-style targets, redirect
  revalidation, timeout, redirect limit, response-size limit, and controlled
  `httpx` execution implemented)
- [x] Workflow execution — Milestone 7 (input schema validation, sequential
  HTTP steps, runtime expressions, step and workflow outputs, success criteria,
  conditional actions, bounded retries, goto/end control flow, request and
  workflow timeouts, structured results, and workflow CLI commands implemented)
- [x] Contract assertions — Milestone 8 (evaluated request parameters,
  required values, request media types and bodies, response status precedence,
  required headers, response media types and bodies, and JSON Schema 2020-12
  validation integrated into workflow execution)
- [x] Mock server and deterministic examples — Milestone 9 (stateless route
  generation, scenario/status selection, named and first examples,
  deterministic schema values, headers, latency, request validation, local
  foreground HTTP serving, and JSON mock manifests implemented)
- [x] Test scenarios and isolation — Milestone 10 (sorted local YAML/JSON
  scenarios, per-run loopback mock server and response selection, workflow
  expectations, fail-fast option, explicit rejection of environment overrides,
  JSON CLI results, and tests)
- [x] Authentication and secret redaction — Milestone 11 (OpenAPI OR/AND
  requirement selection, environment-backed bearer, Basic and API keys,
  explicit workflow SHA-256/origin/method/path bindings, disabled credentialed
  redirects, redacted output and transport diagnostics)
- [x] Reporting — Milestone 12 (traceable per-step metadata and duration,
  Console/JSON/JUnit output, optional escaped HTML with restrictive CSP,
  explicit report output directory and secret-safe result projection)
- [x] Docker and CI execution — Milestone 13 (unprivileged, read-only
  container with read-only input mounts, loopback-only mocks without exposed
  ports, `justfile` recipes, and CI-neutral integration entry point; Docker
  runtime verification requires an environment with Docker installed)
- [x] Reproducible `api-ncpeh` integration source — Milestone 13 (JSL supplies
  the authenticated checkout; the entry point verifies origin URL, Git tag,
  clean checkout, SHA and that configured documents and allowed roots are
  confined to it before validation; no repository credentials enter the tool)
- [x] Exportable mock package and versioned Python/Docker runtime — Milestone
  14 (generate and validate a semantic-versioned package directory, then run
  the same package directly or in a per-version Docker image without runtime
  re-evaluation of source specifications; see
  [`mock-verarbeitungsablauf.md`](architecture/mock-verarbeitungsablauf.md))

## Unresolved technical decisions

Keine offenen technischen Entscheidungen.
