# Copyright (Change Date see Readme), gematik GmbH
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# ******
#
# For additional notes and disclaimer from gematik and in case of changes
# by gematik, find details in the "Readme" file.

"""OpenAPI 3.1 JSON Schema dialect and schema validation."""

from collections.abc import Iterator, Mapping
from typing import Any
from urllib.parse import urlsplit

from jsonschema import Draft7Validator, Draft201909Validator, Draft202012Validator
from jsonschema.exceptions import SchemaError

from ..errors import ExitCode, ToolError
from .model import OpenApiDocument

_DEFAULT_DIALECT = "https://spec.openapis.org/oas/3.1/dialect/base"
_DIALECT_VALIDATORS = {
    _DEFAULT_DIALECT: Draft202012Validator,
    "https://json-schema.org/draft/2020-12/schema": Draft202012Validator,
    "https://json-schema.org/draft/2019-09/schema": Draft201909Validator,
    "http://json-schema.org/draft-07/schema#": Draft7Validator,
}
_HTTP_METHODS = frozenset(
    {"delete", "get", "head", "options", "patch", "post", "put", "trace"}
)


def find_schema_issues(document: OpenApiDocument) -> list[ToolError]:
    """Validate known schema objects using their effective JSON Schema dialect.

    The default OpenAPI 3.1 dialect applies when ``jsonSchemaDialect`` is not
    declared. A root declaration overrides that default and a schema-local
    ``$schema`` declaration overrides the root declaration. Dialects outside
    the explicit local mapping fail rather than triggering a remote lookup.
    """
    root_dialect, root_issues = _resolve_dialect(
        document.raw.get("jsonSchemaDialect", _DEFAULT_DIALECT),
        "$.jsonSchemaDialect",
        document.path,
    )
    if root_dialect is None:
        return root_issues

    issues = root_issues
    for schema, path in _iter_openapi_schemas(document.raw):
        dialect, dialect_issues = _resolve_dialect(
            schema.get("$schema", root_dialect),
            f"{path}.$schema",
            document.path,
        )
        issues.extend(dialect_issues)
        if dialect is None:
            continue

        validator = _DIALECT_VALIDATORS[dialect]
        try:
            validator.check_schema(schema)
        except SchemaError as error:
            issues.append(
                ToolError(
                    "OPENAPI_SCHEMA_INVALID",
                    f"Invalid JSON Schema at {path}: {error.message}",
                    ExitCode.VALIDATION_ERROR,
                    document.path,
                )
            )
    return issues


def _resolve_dialect(
    value: Any, path: str, file_path: str
) -> tuple[str | None, list[ToolError]]:
    if not isinstance(value, str) or not _is_absolute_uri(value):
        return None, [
            ToolError(
                "OPENAPI_JSON_SCHEMA_DIALECT_INVALID",
                f"JSON Schema dialect at {path} must be an absolute URI.",
                ExitCode.VALIDATION_ERROR,
                file_path,
            )
        ]
    if value not in _DIALECT_VALIDATORS:
        return None, [
            ToolError(
                "OPENAPI_JSON_SCHEMA_DIALECT_UNSUPPORTED",
                f"JSON Schema dialect '{value}' at {path} is not supported in V1.",
                ExitCode.VALIDATION_ERROR,
                file_path,
            )
        ]
    return value, []


def _is_absolute_uri(value: str) -> bool:
    parsed = urlsplit(value)
    return bool(parsed.scheme)


def _iter_openapi_schemas(
    document: Mapping[str, Any],
) -> Iterator[tuple[dict[str, Any], str]]:
    components = document.get("components")
    if isinstance(components, Mapping):
        yield from _iter_component_schemas(components)

    paths = document.get("paths")
    if not isinstance(paths, Mapping):
        return
    for path, path_item in paths.items():
        if not isinstance(path_item, Mapping):
            continue
        path_location = f"$.paths.{path}"
        yield from _iter_parameter_schemas(
            path_item.get("parameters"), f"{path_location}.parameters"
        )
        for method, operation in path_item.items():
            if method.lower() not in _HTTP_METHODS or not isinstance(
                operation, Mapping
            ):
                continue
            operation_location = f"{path_location}.{method}"
            yield from _iter_parameter_schemas(
                operation.get("parameters"), f"{operation_location}.parameters"
            )
            yield from _iter_request_body_schemas(
                operation.get("requestBody"), f"{operation_location}.requestBody"
            )
            yield from _iter_response_schemas(
                operation.get("responses"), f"{operation_location}.responses"
            )


def _iter_component_schemas(
    components: Mapping[str, Any],
) -> Iterator[tuple[dict[str, Any], str]]:
    schemas = components.get("schemas")
    if isinstance(schemas, Mapping):
        for name, schema in schemas.items():
            if isinstance(schema, dict):
                yield schema, f"$.components.schemas.{name}"

    yield from _iter_parameter_schemas(
        components.get("parameters"), "$.components.parameters", mapping_values=True
    )
    yield from _iter_header_schemas(
        components.get("headers"), "$.components.headers", mapping_values=True
    )
    yield from _iter_request_body_schemas(
        components.get("requestBodies"),
        "$.components.requestBodies",
        mapping_values=True,
    )
    yield from _iter_response_schemas(
        components.get("responses"), "$.components.responses", mapping_values=True
    )


def _iter_parameter_schemas(
    parameters: Any, path: str, *, mapping_values: bool = False
) -> Iterator[tuple[dict[str, Any], str]]:
    if mapping_values:
        if not isinstance(parameters, Mapping):
            return
        for name, parameter in parameters.items():
            if isinstance(parameter, Mapping) and isinstance(
                parameter.get("schema"), dict
            ):
                yield parameter["schema"], f"{path}.{name}.schema"
        return
    if not isinstance(parameters, (list, tuple)):
        return
    for index, parameter in enumerate(parameters):
        if isinstance(parameter, Mapping) and isinstance(parameter.get("schema"), dict):
            yield parameter["schema"], f"{path}[{index}].schema"


def _iter_header_schemas(
    headers: Any, path: str, *, mapping_values: bool = False
) -> Iterator[tuple[dict[str, Any], str]]:
    if not mapping_values or not isinstance(headers, Mapping):
        return
    for name, header in headers.items():
        if isinstance(header, Mapping) and isinstance(header.get("schema"), dict):
            yield header["schema"], f"{path}.{name}.schema"


def _iter_request_body_schemas(
    request_body: Any, path: str, *, mapping_values: bool = False
) -> Iterator[tuple[dict[str, Any], str]]:
    if mapping_values:
        if not isinstance(request_body, Mapping):
            return
        for name, body in request_body.items():
            if isinstance(body, Mapping):
                yield from _iter_content_schemas(
                    body.get("content"), f"{path}.{name}.content"
                )
        return
    if isinstance(request_body, Mapping):
        yield from _iter_content_schemas(request_body.get("content"), f"{path}.content")


def _iter_response_schemas(
    responses: Any, path: str, *, mapping_values: bool = False
) -> Iterator[tuple[dict[str, Any], str]]:
    response_items = responses.items() if isinstance(responses, Mapping) else ()
    for status, response in response_items:
        response_path = f"{path}.{status}"
        if not isinstance(response, Mapping):
            continue
        yield from _iter_content_schemas(
            response.get("content"), f"{response_path}.content"
        )
        yield from _iter_header_schemas(
            response.get("headers"), f"{response_path}.headers", mapping_values=True
        )


def _iter_content_schemas(
    content: Any, path: str
) -> Iterator[tuple[dict[str, Any], str]]:
    if not isinstance(content, Mapping):
        return
    for media_type, media in content.items():
        if isinstance(media, Mapping) and isinstance(media.get("schema"), dict):
            yield media["schema"], f"{path}.{media_type}.schema"
