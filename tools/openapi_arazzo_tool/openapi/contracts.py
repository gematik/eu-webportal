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

"""Runtime request and response assertions against OpenAPI 3.1 operations."""

import json
from collections.abc import Mapping
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from referencing.exceptions import Unresolvable

from ..errors import ExitCode, ToolError
from ..http.execution import HttpResponse
from ..http.requests import HttpRequest


def validate_request_contract(
    document: Mapping[str, Any],
    path_item: Mapping[str, Any],
    operation: Mapping[str, Any],
    parameter_values: Mapping[tuple[str, str], Any],
    request: HttpRequest,
    body_payload: Any,
    body_content_type: str | None,
) -> None:
    """Validate evaluated request values before network execution."""
    parameters = effective_runtime_parameters(document, path_item, operation)
    normalized_values = {
        ((name.lower(), location) if location == "header" else (name, location)): value
        for (name, location), value in parameter_values.items()
    }
    for key, parameter in parameters.items():
        value = normalized_values.get(key)
        if value is None and key not in normalized_values:
            if parameter.get("required") is True:
                raise _request_error(
                    f"Required parameter '{parameter['name']}' in '{parameter['in']}' is missing."
                )
            continue
        schema = parameter.get("schema")
        if isinstance(schema, Mapping):
            _validate_schema(
                value,
                schema,
                document,
                _request_error,
                f"Parameter '{parameter['name']}'",
            )

    definition = operation.get("requestBody")
    if isinstance(definition, Mapping) and "$ref" in definition:
        definition = _local_ref(document, definition["$ref"], "request body")
    if not isinstance(definition, Mapping):
        if body_content_type is not None:
            raise _request_error("Request body is not defined by the operation.")
        return
    if body_content_type is None:
        if definition.get("required") is True:
            raise _request_error("Required request body is missing.")
        return
    content = definition.get("content")
    media = _matching_media(content, body_content_type)
    if media is None:
        raise _request_error(
            f"Request Content-Type '{body_content_type}' is not defined."
        )
    actual_content_type = (
        request.headers.get("Content-Type", "").partition(";")[0].strip()
    )
    if not _media_matches(body_content_type, actual_content_type):
        raise _request_error(
            f"Serialized request Content-Type '{actual_content_type}' does not match '{body_content_type}'."
        )
    schema = media.get("schema")
    if isinstance(schema, Mapping):
        _validate_schema(body_payload, schema, document, _request_error, "Request body")


def validate_response_contract(
    document: Mapping[str, Any],
    operation: Mapping[str, Any],
    response: HttpResponse,
) -> Any:
    """Validate response selection, headers, media type, body, and schema."""
    definition = select_response_definition(
        operation.get("responses"), response.status_code
    )
    if definition is None:
        raise _response_error(
            f"Status code {response.status_code} is not defined by the operation."
        )
    if "$ref" in definition:
        definition = _local_ref(document, definition["$ref"], "response")

    headers = definition.get("headers")
    if isinstance(headers, Mapping):
        for name, header in headers.items():
            if not isinstance(header, Mapping):
                continue
            if "$ref" in header:
                header = _local_ref(document, header["$ref"], "response header")
            value = response.headers.get(name)
            if value is None:
                if header.get("required") is True:
                    raise _response_error(
                        f"Required response header '{name}' is missing."
                    )
                continue
            schema = header.get("schema")
            if isinstance(schema, Mapping):
                _validate_schema(
                    value,
                    schema,
                    document,
                    _response_error,
                    f"Response header '{name}'",
                )

    content = definition.get("content")
    if not isinstance(content, Mapping) or not content:
        if response.body:
            raise _response_error("Response body is not defined for this status code.")
        return None
    content_type = response.headers.get("content-type")
    if not content_type:
        raise _response_error("Response Content-Type is missing.")
    media = _matching_media(content, content_type)
    if media is None:
        raise _response_error(f"Response Content-Type '{content_type}' is not defined.")
    payload = _decode_body(response.body, content_type)
    schema = media.get("schema")
    if isinstance(schema, Mapping):
        _validate_schema(payload, schema, document, _response_error, "Response body")
    return payload


def select_response_definition(
    responses: Any,
    status_code: int,
) -> Mapping[str, Any] | None:
    """Select explicit, range, then default response definition."""
    if not isinstance(responses, Mapping):
        return None
    explicit = responses.get(str(status_code))
    if isinstance(explicit, Mapping):
        return explicit
    range_key = f"{status_code // 100}XX"
    for key, value in responses.items():
        if (
            isinstance(key, str)
            and key.upper() == range_key
            and isinstance(value, Mapping)
        ):
            return value
    default = responses.get("default")
    return default if isinstance(default, Mapping) else None


def effective_runtime_parameters(
    document: Mapping[str, Any],
    path_item: Mapping[str, Any],
    operation: Mapping[str, Any],
) -> dict[tuple[str, str], Mapping[str, Any]]:
    """Return effective inline and local-reference Parameter Objects."""
    result: dict[tuple[str, str], Mapping[str, Any]] = {}
    for owner in (path_item, operation):
        values = owner.get("parameters")
        if not isinstance(values, list):
            continue
        for parameter in values:
            if not isinstance(parameter, Mapping):
                continue
            if "$ref" in parameter:
                parameter = _local_ref(document, parameter["$ref"], "parameter")
            name = parameter.get("name")
            location = parameter.get("in")
            if not isinstance(name, str) or not isinstance(location, str):
                continue
            key = (name.lower(), location) if location == "header" else (name, location)
            result[key] = parameter
    return result


def _matching_media(content: Any, content_type: str) -> Mapping[str, Any] | None:
    if not isinstance(content, Mapping):
        return None
    actual = content_type.partition(";")[0].strip().lower()
    exact = next(
        (
            media
            for name, media in content.items()
            if isinstance(name, str)
            and name.lower() == actual
            and isinstance(media, Mapping)
        ),
        None,
    )
    if exact is not None:
        return exact
    major = actual.partition("/")[0]
    ranged = next(
        (
            media
            for name, media in content.items()
            if isinstance(name, str)
            and name.lower() == f"{major}/*"
            and isinstance(media, Mapping)
        ),
        None,
    )
    if isinstance(ranged, Mapping):
        return ranged
    wildcard = next(
        (
            media
            for name, media in content.items()
            if isinstance(name, str) and name == "*/*" and isinstance(media, Mapping)
        ),
        None,
    )
    return wildcard if isinstance(wildcard, Mapping) else None


def _media_matches(expected: str, actual: str) -> bool:
    expected_base = expected.partition(";")[0].strip().lower()
    actual_base = actual.partition(";")[0].strip().lower()
    return (
        expected_base == actual_base
        or expected_base == "*/*"
        or expected_base.endswith("/*")
        and actual_base.startswith(expected_base[:-1])
    )


def _decode_body(body: bytes, content_type: str) -> Any:
    media_type = content_type.partition(";")[0].strip().lower()
    if not body:
        return None
    if media_type == "application/json" or media_type.endswith("+json"):
        try:
            return json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise _response_error("Response body is not valid JSON.") from error
    if media_type.startswith("text/") or media_type in {
        "application/xml",
        "application/xhtml+xml",
    }:
        try:
            return body.decode("utf-8")
        except UnicodeDecodeError as error:
            raise _response_error("Response body is not valid UTF-8 text.") from error
    return body


def _validate_schema(
    instance: Any,
    schema: Mapping[str, Any],
    document: Mapping[str, Any],
    error_factory: Any,
    label: str,
) -> None:
    try:
        Draft202012Validator(document).evolve(schema=schema).validate(instance)
    except ValidationError as error:
        raise error_factory(f"{label} violates its schema: {error.message}.") from error
    except Unresolvable as error:
        raise error_factory(
            f"{label} schema reference cannot be resolved in memory: {error}."
        ) from error


def _local_ref(
    document: Mapping[str, Any],
    ref: Any,
    label: str,
) -> Mapping[str, Any]:
    if not isinstance(ref, str) or not ref.startswith("#/"):
        raise _response_error(f"Runtime {label} reference must be local.")
    value: Any = document
    for token in ref[2:].split("/"):
        name = token.replace("~1", "/").replace("~0", "~")
        value = value.get(name) if isinstance(value, Mapping) else None
        if value is None:
            raise _response_error(
                f"Runtime {label} reference '{ref}' cannot be resolved."
            )
    if not isinstance(value, Mapping):
        raise _response_error(f"Runtime {label} reference '{ref}' is not an object.")
    return value


def _request_error(message: str) -> ToolError:
    return ToolError("OPENAPI_REQUEST_CONTRACT_VIOLATION", message, ExitCode.TEST_ERROR)


def _response_error(message: str) -> ToolError:
    return ToolError(
        "OPENAPI_RESPONSE_CONTRACT_VIOLATION", message, ExitCode.TEST_ERROR
    )
