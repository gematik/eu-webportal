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

"""OpenAPI 3.1 Response Object validation."""

import re
from collections.abc import Mapping
from typing import Any

from ..errors import ExitCode, ToolError
from .model import OpenApiDocument

_HTTP_METHODS = frozenset(
    {"delete", "get", "head", "options", "patch", "post", "put", "trace"}
)
_STATUS_CODE_PATTERN = re.compile(r"^[1-5]\d{2}$")
_STATUS_RANGE_PATTERN = re.compile(r"^[1-5][Xx]{2}$")


def find_response_issues(document: OpenApiDocument) -> list[ToolError]:
    """Validate reusable and operation-level Response Objects.

    Contract assertion and mock response selection are intentionally deferred.
    This validator only ensures that declared response definitions have valid
    OpenAPI structure and usable explicit, range, or default response keys.
    """
    issues: list[ToolError] = []
    components = document.raw.get("components")
    if isinstance(components, Mapping):
        _validate_responses(
            components.get("responses"),
            "$.components.responses",
            document.path,
            issues,
            validate_status_keys=False,
        )

    paths = document.raw.get("paths")
    if not isinstance(paths, Mapping):
        return issues
    for path, path_item in paths.items():
        if not isinstance(path, str) or not isinstance(path_item, Mapping):
            continue
        for method, operation in path_item.items():
            if method.lower() not in _HTTP_METHODS or not isinstance(
                operation, Mapping
            ):
                continue
            location = f"$.paths.{path}.{method}.responses"
            _validate_responses(
                operation.get("responses"), location, document.path, issues
            )
    return issues


def _validate_responses(
    responses: Any,
    path: str,
    file_path: str,
    issues: list[ToolError],
    *,
    validate_status_keys: bool = True,
) -> None:
    if not isinstance(responses, Mapping):
        return
    if not responses:
        _add_issue(
            issues,
            path,
            "Responses Object must define at least one response.",
            file_path,
        )
    for status, response in responses.items():
        response_path = f"{path}.{status}"
        if validate_status_keys and not _is_response_key(status):
            _add_issue(
                issues,
                response_path,
                "Response key must be a three-digit status code, an HTTP status-code range, or 'default'.",
                file_path,
            )
        _validate_response(response, response_path, file_path, issues)


def _validate_response(
    response: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if not isinstance(response, Mapping):
        _add_issue(issues, path, "Response must be a mapping or a $ref.", file_path)
        return
    if "$ref" in response:
        return
    description = response.get("description")
    if not isinstance(description, str) or not description.strip():
        _add_issue(
            issues,
            f"{path}.description",
            "Response description must be a non-empty string.",
            file_path,
        )
    _validate_mapping(
        response.get("headers"),
        f"{path}.headers",
        "Response headers",
        file_path,
        issues,
    )
    _validate_content(response.get("content"), f"{path}.content", file_path, issues)


def _validate_content(
    content: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if content is None:
        return
    if not isinstance(content, Mapping):
        _add_issue(issues, path, "Response content must be a mapping.", file_path)
        return
    for media_type, media in content.items():
        media_path = f"{path}.{media_type}"
        if not isinstance(media_type, str) or not media_type.strip():
            _add_issue(
                issues,
                media_path,
                "Media type keys must be non-empty strings.",
                file_path,
            )
        if not isinstance(media, Mapping):
            _add_issue(
                issues, media_path, "Media Type Object must be a mapping.", file_path
            )


def _validate_mapping(
    value: Any, path: str, label: str, file_path: str, issues: list[ToolError]
) -> None:
    if value is not None and not isinstance(value, Mapping):
        _add_issue(issues, path, f"{label} must be a mapping.", file_path)


def _is_response_key(value: Any) -> bool:
    return isinstance(value, str) and (
        value == "default"
        or bool(_STATUS_CODE_PATTERN.fullmatch(value))
        or bool(_STATUS_RANGE_PATTERN.fullmatch(value))
    )


def _add_issue(
    issues: list[ToolError], path: str, message: str, file_path: str
) -> None:
    issues.append(
        ToolError(
            "OPENAPI_RESPONSE_INVALID",
            f"{message} Found at {path}.",
            ExitCode.VALIDATION_ERROR,
            file_path,
        )
    )
