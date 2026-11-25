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

"""OpenAPI 3.1 Example Object validation."""

from collections.abc import Mapping, Sequence
from typing import Any

from ..errors import ExitCode, ToolError
from .model import OpenApiDocument

_HTTP_METHODS = frozenset(
    {"delete", "get", "head", "options", "patch", "post", "put", "trace"}
)


def find_example_issues(document: OpenApiDocument) -> list[ToolError]:
    """Validate inline, reusable, and named OpenAPI examples.

    External example values are deliberately not fetched in validation. This
    protects the tool from untrusted network/file access; later mock loading
    will resolve external values through an explicit security policy.
    """
    issues: list[ToolError] = []
    components = document.raw.get("components")
    if isinstance(components, Mapping):
        _validate_components(components, document.path, issues)
    paths = document.raw.get("paths")
    if isinstance(paths, Mapping):
        _validate_paths(paths, document.path, issues)
    return issues


def _validate_components(
    components: Mapping[str, Any], file_path: str, issues: list[ToolError]
) -> None:
    _validate_named_examples(
        components.get("examples"), "$.components.examples", file_path, issues
    )
    _validate_parameter_map(
        components.get("parameters"), "$.components.parameters", file_path, issues
    )
    _validate_header_map(
        components.get("headers"), "$.components.headers", file_path, issues
    )
    _validate_request_body_map(
        components.get("requestBodies"), "$.components.requestBodies", file_path, issues
    )
    _validate_response_map(
        components.get("responses"), "$.components.responses", file_path, issues
    )


def _validate_paths(
    paths: Mapping[str, Any], file_path: str, issues: list[ToolError]
) -> None:
    for path, path_item in paths.items():
        if not isinstance(path, str) or not isinstance(path_item, Mapping):
            continue
        path_location = f"$.paths.{path}"
        _validate_parameter_list(
            path_item.get("parameters"),
            f"{path_location}.parameters",
            file_path,
            issues,
        )
        for method, operation in path_item.items():
            if method.lower() not in _HTTP_METHODS or not isinstance(
                operation, Mapping
            ):
                continue
            location = f"{path_location}.{method}"
            _validate_parameter_list(
                operation.get("parameters"), f"{location}.parameters", file_path, issues
            )
            _validate_request_body(
                operation.get("requestBody"),
                f"{location}.requestBody",
                file_path,
                issues,
            )
            _validate_response_map(
                operation.get("responses"), f"{location}.responses", file_path, issues
            )


def _validate_parameter_map(
    parameters: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if not isinstance(parameters, Mapping):
        return
    for name, parameter in parameters.items():
        _validate_parameter(parameter, f"{path}.{name}", file_path, issues)


def _validate_parameter_list(
    parameters: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if not _is_sequence(parameters):
        return
    for index, parameter in enumerate(parameters):
        _validate_parameter(parameter, f"{path}[{index}]", file_path, issues)


def _validate_parameter(
    parameter: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if isinstance(parameter, Mapping) and "$ref" not in parameter:
        _validate_example_fields(parameter, path, file_path, issues)
        _validate_content(
            parameter.get("content"), f"{path}.content", file_path, issues
        )


def _validate_header_map(
    headers: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if not isinstance(headers, Mapping):
        return
    for name, header in headers.items():
        if isinstance(header, Mapping) and "$ref" not in header:
            _validate_example_fields(header, f"{path}.{name}", file_path, issues)
            _validate_content(
                header.get("content"), f"{path}.{name}.content", file_path, issues
            )


def _validate_request_body_map(
    bodies: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if not isinstance(bodies, Mapping):
        return
    for name, body in bodies.items():
        _validate_request_body(body, f"{path}.{name}", file_path, issues)


def _validate_request_body(
    body: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if isinstance(body, Mapping) and "$ref" not in body:
        _validate_content(body.get("content"), f"{path}.content", file_path, issues)


def _validate_response_map(
    responses: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if not isinstance(responses, Mapping):
        return
    for status, response in responses.items():
        if not isinstance(response, Mapping) or "$ref" in response:
            continue
        response_path = f"{path}.{status}"
        _validate_content(
            response.get("content"), f"{response_path}.content", file_path, issues
        )
        _validate_header_map(
            response.get("headers"), f"{response_path}.headers", file_path, issues
        )


def _validate_content(
    content: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if not isinstance(content, Mapping):
        return
    for media_type, media in content.items():
        if isinstance(media, Mapping):
            _validate_example_fields(media, f"{path}.{media_type}", file_path, issues)


def _validate_example_fields(
    node: Mapping[str, Any], path: str, file_path: str, issues: list[ToolError]
) -> None:
    if "example" in node and "examples" in node:
        _add_issue(
            issues, path, "example and examples are mutually exclusive.", file_path
        )
    _validate_named_examples(
        node.get("examples"), f"{path}.examples", file_path, issues
    )


def _validate_named_examples(
    examples: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if examples is None:
        return
    if not isinstance(examples, Mapping):
        _add_issue(issues, path, "Examples must be a mapping.", file_path)
        return
    for name, example in examples.items():
        _validate_example(example, f"{path}.{name}", file_path, issues)


def _validate_example(
    example: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if not isinstance(example, Mapping):
        _add_issue(issues, path, "Example must be a mapping or a $ref.", file_path)
        return
    if "$ref" in example:
        return
    if "value" in example and "externalValue" in example:
        _add_issue(
            issues,
            path,
            "Example value and externalValue are mutually exclusive.",
            file_path,
        )


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


def _add_issue(
    issues: list[ToolError], path: str, message: str, file_path: str
) -> None:
    issues.append(
        ToolError(
            "OPENAPI_EXAMPLE_INVALID",
            f"{message} Found at {path}.",
            ExitCode.VALIDATION_ERROR,
            file_path,
        )
    )
