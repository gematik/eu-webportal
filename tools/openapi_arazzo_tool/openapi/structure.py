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

"""Basic OpenAPI 3.1 document structure validation."""

from collections.abc import Mapping
from typing import Any

from ..errors import ExitCode, ToolError
from .model import OpenApiDocument

_HTTP_METHODS = frozenset(
    {"delete", "get", "head", "options", "patch", "post", "put", "trace"}
)


def find_structure_issues(document: OpenApiDocument) -> list[ToolError]:
    """Return basic OpenAPI document-structure diagnostics.

    This deliberately validates only OpenAPI object boundaries required before
    deeper validations can trust their input. Parameter, request body, and
    response-content semantics remain separate Milestone 1 increments.
    """
    raw = document.raw
    issues: list[ToolError] = []
    _require_mapping(raw.get("info"), "$.info", "Info Object", document.path, issues)
    info = raw.get("info")
    if isinstance(info, Mapping):
        _require_non_empty_string(
            info.get("title"), "$.info.title", "Info title", document.path, issues
        )
        _require_non_empty_string(
            info.get("version"), "$.info.version", "Info version", document.path, issues
        )

    paths = raw.get("paths")
    if paths is not None and not isinstance(paths, Mapping):
        _add_issue(issues, "$.paths", "Paths Object must be a mapping.", document.path)
    if isinstance(paths, Mapping):
        _validate_paths(paths, document.path, issues)

    components = raw.get("components")
    if components is not None and not isinstance(components, Mapping):
        _add_issue(
            issues,
            "$.components",
            "Components Object must be a mapping.",
            document.path,
        )
    return issues


def _validate_paths(
    paths: Mapping[str, Any], file_path: str, issues: list[ToolError]
) -> None:
    for path, path_item in paths.items():
        location = f"$.paths.{path}"
        if not isinstance(path, str) or not path.startswith("/"):
            _add_issue(issues, location, "Path keys must begin with '/'.", file_path)
            continue
        if not isinstance(path_item, Mapping):
            _add_issue(
                issues, location, "Path Item Object must be a mapping.", file_path
            )
            continue
        for method, operation in path_item.items():
            if method.lower() not in _HTTP_METHODS:
                continue
            operation_location = f"{location}.{method}"
            if not isinstance(operation, Mapping):
                _add_issue(
                    issues,
                    operation_location,
                    "Operation Object must be a mapping.",
                    file_path,
                )
                continue
            responses = operation.get("responses")
            if not isinstance(responses, Mapping):
                _add_issue(
                    issues,
                    f"{operation_location}.responses",
                    "Operation Object requires a Responses Object mapping.",
                    file_path,
                )


def _require_mapping(
    value: Any, path: str, label: str, file_path: str, issues: list[ToolError]
) -> None:
    if not isinstance(value, Mapping):
        _add_issue(issues, path, f"{label} must be a mapping.", file_path)


def _require_non_empty_string(
    value: Any, path: str, label: str, file_path: str, issues: list[ToolError]
) -> None:
    if not isinstance(value, str) or not value.strip():
        _add_issue(issues, path, f"{label} must be a non-empty string.", file_path)


def _add_issue(
    issues: list[ToolError], path: str, message: str, file_path: str
) -> None:
    issues.append(
        ToolError(
            "OPENAPI_STRUCTURE_INVALID",
            f"{message} Found at {path}.",
            ExitCode.VALIDATION_ERROR,
            file_path,
        )
    )
