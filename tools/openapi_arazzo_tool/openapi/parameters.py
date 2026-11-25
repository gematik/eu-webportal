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

"""OpenAPI 3.1 Parameter Object validation."""

import re
from collections.abc import Mapping, Sequence
from typing import Any

from ..errors import ExitCode, ToolError
from .model import OpenApiDocument

_HTTP_METHODS = frozenset(
    {"delete", "get", "head", "options", "patch", "post", "put", "trace"}
)
_LOCATIONS = frozenset({"path", "query", "header", "cookie"})
_PATH_TEMPLATE_PATTERN = re.compile(r"\{([^{}]+)\}")


def find_parameter_issues(document: OpenApiDocument) -> list[ToolError]:
    """Validate inline and reusable Parameter Objects.

    The check enforces OpenAPI's required Parameter Object fields and
    invariants. `$ref` Parameter Objects are not duplicated here: recursive
    reference resolution already validates that they are safe and resolvable;
    subsequent internal-model work will apply these rules to dereferenced
    parameter values as well.
    """
    issues: list[ToolError] = []
    components = document.raw.get("components")
    if isinstance(components, Mapping):
        _validate_component_parameters(
            components.get("parameters"), document.path, issues
        )

    paths = document.raw.get("paths")
    if isinstance(paths, Mapping):
        _validate_path_parameters(paths, document.path, issues)
    return issues


def _validate_component_parameters(
    parameters: Any, file_path: str, issues: list[ToolError]
) -> None:
    if not isinstance(parameters, Mapping):
        return
    for name, parameter in parameters.items():
        _validate_parameter(
            parameter, f"$.components.parameters.{name}", file_path, issues
        )


def _validate_path_parameters(
    paths: Mapping[str, Any], file_path: str, issues: list[ToolError]
) -> None:
    for path, path_item in paths.items():
        if not isinstance(path, str) or not isinstance(path_item, Mapping):
            continue
        path_location = f"$.paths.{path}"
        path_parameters = _validate_parameter_list(
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
            operation_location = f"{path_location}.{method}"
            operation_parameters = _validate_parameter_list(
                operation.get("parameters"),
                f"{operation_location}.parameters",
                file_path,
                issues,
            )
            _validate_template_parameters(
                path,
                path_parameters,
                operation_parameters,
                operation_location,
                file_path,
                issues,
            )


def _validate_parameter_list(
    parameters: Any, path: str, file_path: str, issues: list[ToolError]
) -> dict[tuple[str, str], Mapping[str, Any]]:
    if parameters is None:
        return {}
    if not _is_sequence(parameters):
        _add_issue(issues, path, "Parameters must be an array.", file_path)
        return {}

    found: dict[tuple[str, str], Mapping[str, Any]] = {}
    for index, parameter in enumerate(parameters):
        parameter_path = f"{path}[{index}]"
        if not isinstance(parameter, Mapping):
            _add_issue(
                issues,
                parameter_path,
                "Parameter must be a mapping or a $ref.",
                file_path,
            )
            continue
        if "$ref" in parameter:
            continue
        key = _validate_parameter(parameter, parameter_path, file_path, issues)
        if key is None:
            continue
        if key in found:
            _add_issue(
                issues,
                parameter_path,
                f"Duplicate parameter '{key[0]}' in '{key[1]}'; each (name, in) pair must be unique.",
                file_path,
            )
        else:
            found[key] = parameter
    return found


def _validate_parameter(
    parameter: Any, path: str, file_path: str, issues: list[ToolError]
) -> tuple[str, str] | None:
    if not isinstance(parameter, Mapping):
        _add_issue(issues, path, "Parameter must be a mapping or a $ref.", file_path)
        return None
    if "$ref" in parameter:
        return None

    name = parameter.get("name")
    location = parameter.get("in")
    valid_name = isinstance(name, str) and bool(name.strip())
    valid_location = isinstance(location, str) and location in _LOCATIONS
    if not valid_name:
        _add_issue(
            issues,
            f"{path}.name",
            "Parameter name must be a non-empty string.",
            file_path,
        )
    if not valid_location:
        _add_issue(
            issues,
            f"{path}.in",
            "Parameter location must be one of path, query, header, or cookie.",
            file_path,
        )

    has_schema = "schema" in parameter
    has_content = "content" in parameter
    if has_schema == has_content:
        _add_issue(
            issues,
            path,
            "Parameter must define exactly one of schema or content.",
            file_path,
        )
    if location == "path" and parameter.get("required") is not True:
        _add_issue(
            issues,
            f"{path}.required",
            "Path parameters must set required to true.",
            file_path,
        )

    if not valid_name or not valid_location:
        return None
    if not isinstance(name, str) or not isinstance(location, str):
        return None
    return name, location


def _validate_template_parameters(
    path: str,
    path_parameters: Mapping[tuple[str, str], Mapping[str, Any]],
    operation_parameters: Mapping[tuple[str, str], Mapping[str, Any]],
    operation_path: str,
    file_path: str,
    issues: list[ToolError],
) -> None:
    effective_parameters = {**path_parameters, **operation_parameters}
    template_names = set(_PATH_TEMPLATE_PATTERN.findall(path))
    for name in template_names:
        if (name, "path") not in effective_parameters:
            _add_issue(
                issues,
                operation_path,
                f"Path template parameter '{name}' has no matching path Parameter Object.",
                file_path,
            )
    for name, location in effective_parameters:
        if location == "path" and name not in template_names:
            _add_issue(
                issues,
                operation_path,
                f"Path Parameter Object '{name}' has no matching path template expression.",
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
            "OPENAPI_PARAMETER_INVALID",
            f"{message} Found at {path}.",
            ExitCode.VALIDATION_ERROR,
            file_path,
        )
    )
