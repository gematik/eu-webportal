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

"""Deterministic mock route and response generation."""

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..errors import ExitCode, ToolError
from ..http.execution import HttpResponse
from ..openapi.contracts import select_response_definition, validate_response_contract
from ..openapi.model import OpenApiDocument
from .patterns import format_value, pattern_value

_HTTP_METHODS = frozenset(
    {"delete", "get", "head", "options", "patch", "post", "put", "trace"}
)
_PATH_PARAMETER = re.compile(r"\{([^{}]+)\}")
_HEADER_NAME = re.compile(r"^[!#$%&'*+\-.^_`|~A-Za-z0-9]+$")
_MANAGED_HEADERS = frozenset({"connection", "content-length", "transfer-encoding"})


@dataclass(frozen=True)
class MockResponse:
    """Fully materialized deterministic HTTP response."""

    status_code: int
    headers: Mapping[str, str]
    body: bytes


@dataclass(frozen=True)
class MockRoute:
    """Stateless route generated from one OpenAPI operation."""

    method: str
    path_template: str
    operation_id: str
    document: Mapping[str, Any]
    path_item: Mapping[str, Any]
    operation: Mapping[str, Any]
    response: MockResponse
    delay_seconds: float = 0.0
    path_pattern: re.Pattern[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        escaped = re.escape(self.path_template)
        pattern = _PATH_PARAMETER.sub(
            lambda match: f"(?P<{match.group(1)}>[^/]+)",
            escaped.replace(r"\{", "{").replace(r"\}", "}"),
        )
        object.__setattr__(self, "path_pattern", re.compile(f"^{pattern}$"))


def generate_mock_routes(
    documents: list[OpenApiDocument],
    *,
    scenario: Mapping[str, Any] | None = None,
    example_names: Mapping[str, str] | None = None,
    seed: int = 0,
) -> tuple[MockRoute, ...]:
    """Generate routes and selected responses in stable document order."""
    routes: list[MockRoute] = []
    seen: set[tuple[str, str]] = set()
    operation_ids: set[str] = set()
    for loaded in documents:
        paths = loaded.raw.get("paths")
        if not isinstance(paths, Mapping):
            continue
        for path, path_item in paths.items():
            if not isinstance(path, str) or not isinstance(path_item, Mapping):
                continue
            for method, operation in path_item.items():
                if method.lower() not in _HTTP_METHODS or not isinstance(
                    operation, Mapping
                ):
                    continue
                key = (method.upper(), path)
                if key in seen:
                    raise _mock_error(f"Duplicate mock route {key[0]} {key[1]}.")
                seen.add(key)
                operation_id = operation.get("operationId")
                if not isinstance(operation_id, str):
                    raise _mock_error(
                        f"Mocked operation {key[0]} {key[1]} requires operationId."
                    )
                operation_ids.add(operation_id)
                selection = (
                    scenario.get(operation_id)
                    if isinstance(scenario, Mapping)
                    else None
                )
                response, delay = _select_response(
                    loaded.raw,
                    operation,
                    selection if isinstance(selection, Mapping) else None,
                    (example_names or {}).get(operation_id),
                    seed,
                )
                routes.append(
                    MockRoute(
                        key[0],
                        path,
                        operation_id,
                        loaded.raw,
                        path_item,
                        operation,
                        response,
                        delay,
                    )
                )
    if scenario and set(scenario) - operation_ids:
        raise _mock_error("Mock scenario selects an unknown operationId.")
    if example_names and set(example_names) - operation_ids:
        raise _mock_error("Mock examples select an unknown operationId.")
    return tuple(routes)


def mock_manifest(routes: tuple[MockRoute, ...]) -> list[dict[str, Any]]:
    """Return deterministic JSON-compatible generated mock metadata."""
    return [
        {
            "method": route.method,
            "path": route.path_template,
            "operationId": route.operation_id,
            "response": {
                "status": route.response.status_code,
                "headers": dict(route.response.headers),
                "body": _manifest_body(route.response),
            },
            "delayMs": int(route.delay_seconds * 1000),
        }
        for route in routes
    ]


def _select_response(
    document: Mapping[str, Any],
    operation: Mapping[str, Any],
    scenario: Mapping[str, Any] | None,
    explicit_example: str | None,
    seed: int,
) -> tuple[MockResponse, float]:
    status = _selected_status(operation.get("responses"), scenario)
    definition = select_response_definition(operation.get("responses"), status)
    if definition is None:
        raise _mock_error(f"No response definition can produce status {status}.")
    if "$ref" in definition:
        definition = _local_ref(document, definition["$ref"], "response")
    content = definition.get("content")
    headers = _response_headers(document, definition.get("headers"))
    if scenario and isinstance(scenario.get("headers"), Mapping):
        headers.update(
            {str(name): str(value) for name, value in scenario["headers"].items()}
        )
    headers = _validated_headers(headers)
    delay_ms = scenario.get("delayMs", 0) if scenario else 0
    if (
        not isinstance(delay_ms, (int, float))
        or isinstance(delay_ms, bool)
        or delay_ms < 0
    ):
        raise _mock_error("Mock scenario delayMs must be a non-negative number.")
    if not isinstance(content, Mapping) or not content:
        response = MockResponse(status, headers, b"")
        _validate_generated_response(document, operation, response)
        return response, float(delay_ms) / 1000

    media_type, media = next(
        (
            (name, value)
            for name, value in content.items()
            if isinstance(value, Mapping)
        ),
        (None, None),
    )
    if not isinstance(media_type, str) or media is None:
        raise _mock_error(f"Response {status} has no usable media type.")
    example_name = scenario.get("example") if scenario else explicit_example
    value = _select_example(document, media, example_name, seed)
    body = _serialize_body(value, media_type)
    headers.setdefault("Content-Type", media_type)
    response = MockResponse(status, headers, body)
    _validate_generated_response(document, operation, response)
    return response, float(delay_ms) / 1000


def _selected_status(responses: Any, scenario: Mapping[str, Any] | None) -> int:
    if scenario and "response" in scenario:
        status = scenario["response"]
        if (
            not isinstance(status, int)
            or isinstance(status, bool)
            or not 100 <= status <= 599
        ):
            raise _mock_error("Mock scenario response must be an HTTP status integer.")
        return status
    if not isinstance(responses, Mapping):
        raise _mock_error("Operation has no Responses Object.")
    explicit = sorted(
        int(key)
        for key in responses
        if isinstance(key, str) and re.fullmatch(r"[1-5]\d{2}", key)
    )
    successes = [status for status in explicit if 200 <= status < 300]
    if successes:
        return successes[0]
    if explicit:
        return explicit[0]
    ranges = sorted(
        int(key[0]) * 100
        for key in responses
        if isinstance(key, str) and re.fullmatch(r"[1-5][Xx]{2}", key)
    )
    if ranges:
        return next((status for status in ranges if 200 <= status < 300), ranges[0])
    raise _mock_error("A default-only response requires an explicit scenario status.")


def _select_example(
    document: Mapping[str, Any],
    media: Mapping[str, Any],
    example_name: Any,
    seed: int,
) -> Any:
    examples = media.get("examples")
    if example_name is not None:
        if (
            not isinstance(example_name, str)
            or not isinstance(examples, Mapping)
            or example_name not in examples
        ):
            raise _mock_error(
                f"Named response example '{example_name}' does not exist."
            )
        return _example_value(document, examples[example_name])
    if isinstance(examples, Mapping) and examples:
        return _example_value(document, next(iter(examples.values())))
    if "example" in media:
        return media["example"]
    schema = media.get("schema")
    if isinstance(schema, Mapping):
        return _generate_schema_value(document, schema, seed)
    raise _mock_error("Response has no example or schema-generated value.")


def _example_value(document: Mapping[str, Any], example: Any) -> Any:
    if not isinstance(example, Mapping):
        raise _mock_error("Example Object must be a mapping.")
    if "$ref" in example:
        example = _local_ref(document, example["$ref"], "example")
    if "value" in example:
        return example["value"]
    if "externalValue" in example:
        raise _mock_error("External example values are not supported by V1 mocking.")
    raise _mock_error("Example Object has no inline value.")


def _generate_schema_value(
    document: Mapping[str, Any],
    schema: Mapping[str, Any],
    seed: int,
) -> Any:
    if "$ref" in schema:
        schema = _local_ref(document, schema["$ref"], "schema")
    for field_name in ("const", "example", "default"):
        if field_name in schema:
            return schema[field_name]
    enum = schema.get("enum")
    if isinstance(enum, list) and enum:
        return enum[0]
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        schema_type = next((item for item in schema_type if item != "null"), "null")
    if schema_type == "object" or isinstance(schema.get("properties"), Mapping):
        properties = schema.get("properties")
        if not isinstance(properties, Mapping):
            return {}
        required = schema.get("required")
        names = required if isinstance(required, list) else list(properties)
        return {
            name: _generate_schema_value(document, properties[name], seed)
            for name in names
            if name in properties and isinstance(properties[name], Mapping)
        }
    if schema_type == "array":
        items = schema.get("items")
        count = max(int(schema.get("minItems", 1)), 1)
        return (
            [_generate_schema_value(document, items, seed) for _ in range(count)]
            if isinstance(items, Mapping)
            else []
        )
    if schema_type == "integer":
        return int(schema.get("minimum", seed))
    if schema_type == "number":
        return float(schema.get("minimum", seed))
    if schema_type == "boolean":
        return False
    if schema_type == "null":
        return None
    if schema_type == "string" or schema_type is None:
        return _generate_string_value(schema, seed)
    raise _mock_error(
        f"Schema type '{schema_type}' cannot be generated deterministically."
    )


def _generate_string_value(schema: Mapping[str, Any], seed: int) -> str:
    minimum = schema.get("minLength", 0)
    minimum = (
        minimum if isinstance(minimum, int) and not isinstance(minimum, bool) else 0
    )
    pattern = schema.get("pattern")
    if pattern is not None:
        value = pattern_value(pattern)
        if value is None:
            raise _mock_error(
                f"String pattern '{pattern}' is not supported by deterministic generation; "
                "provide an example for this response."
            )
        return value
    formatted = format_value(schema.get("format"))
    if formatted is not None:
        return formatted
    return f"mock-{seed}".ljust(minimum, "x")


def _response_headers(document: Mapping[str, Any], value: Any) -> dict[str, str]:
    headers: dict[str, str] = {}
    if not isinstance(value, Mapping):
        return headers
    for name, header in value.items():
        if not isinstance(header, Mapping):
            continue
        if "$ref" in header:
            header = _local_ref(document, header["$ref"], "header")
        if "example" in header:
            headers[name] = str(header["example"])
        elif isinstance(header.get("schema"), Mapping):
            headers[name] = str(_generate_schema_value(document, header["schema"], 0))
    return headers


def _validated_headers(headers: Mapping[str, str]) -> dict[str, str]:
    validated: dict[str, str] = {}
    normalized: set[str] = set()
    for name, value in headers.items():
        lower_name = name.lower()
        if not _HEADER_NAME.fullmatch(name) or "\r" in value or "\n" in value:
            raise _mock_error(f"Mock response header '{name}' is invalid.")
        if lower_name in _MANAGED_HEADERS:
            raise _mock_error(
                f"Mock response header '{name}' is managed by the server."
            )
        if lower_name in normalized:
            raise _mock_error(
                f"Mock response header '{name}' is duplicated case-insensitively."
            )
        normalized.add(lower_name)
        validated[name] = value
    return validated


def _local_ref(document: Mapping[str, Any], ref: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(ref, str) or not ref.startswith("#/"):
        raise _mock_error(f"Mock {label} reference must be local.")
    value: Any = document
    for token in ref[2:].split("/"):
        value = (
            value.get(token.replace("~1", "/").replace("~0", "~"))
            if isinstance(value, Mapping)
            else None
        )
    if not isinstance(value, Mapping):
        raise _mock_error(f"Mock {label} reference '{ref}' cannot be resolved.")
    return value


def _serialize_body(value: Any, media_type: str) -> bytes:
    normalized = media_type.partition(";")[0].strip().lower()
    if normalized == "application/json" or normalized.endswith("+json"):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    if isinstance(value, str):
        return value.encode()
    if isinstance(value, bytes):
        return value
    raise _mock_error(f"Mock value for '{media_type}' must be text or bytes.")


def _manifest_body(response: MockResponse) -> Any:
    content_type = response.headers.get("Content-Type", "")
    if content_type.partition(";")[0].endswith("json"):
        return json.loads(response.body) if response.body else None
    return response.body.decode("utf-8", errors="replace")


def _validate_generated_response(
    document: Mapping[str, Any],
    operation: Mapping[str, Any],
    response: MockResponse,
) -> None:
    try:
        validate_response_contract(
            document,
            operation,
            HttpResponse(
                response.status_code,
                httpx.Headers(response.headers),
                response.body,
                "mock://generated",
            ),
        )
    except ToolError as error:
        raise _mock_error(
            f"Generated response violates OpenAPI: {error.message}"
        ) from error


def _mock_error(message: str) -> ToolError:
    return ToolError("MOCK_GENERATION_FAILED", message, ExitCode.TEST_ERROR)
