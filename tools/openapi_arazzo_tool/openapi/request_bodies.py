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

"""OpenAPI 3.1 Request Body Object validation."""

from collections.abc import Mapping
from typing import Any

from ..errors import ExitCode, ToolError
from .model import OpenApiDocument

_HTTP_METHODS = frozenset(
    {"delete", "get", "head", "options", "patch", "post", "put", "trace"}
)


def find_request_body_issues(document: OpenApiDocument) -> list[ToolError]:
    """Validate reusable and operation-level Request Body Objects."""
    issues: list[ToolError] = []
    components = document.raw.get("components")
    if isinstance(components, Mapping):
        request_bodies = components.get("requestBodies")
        if isinstance(request_bodies, Mapping):
            for name, request_body in request_bodies.items():
                _validate_request_body(
                    request_body,
                    f"$.components.requestBodies.{name}",
                    document.path,
                    issues,
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
            if "requestBody" in operation:
                _validate_request_body(
                    operation["requestBody"],
                    f"$.paths.{path}.{method}.requestBody",
                    document.path,
                    issues,
                )
    return issues


def _validate_request_body(
    request_body: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if not isinstance(request_body, Mapping):
        _add_issue(issues, path, "Request Body must be a mapping or a $ref.", file_path)
        return
    if "$ref" in request_body:
        return

    required = request_body.get("required")
    if required is not None and not isinstance(required, bool):
        _add_issue(
            issues,
            f"{path}.required",
            "Request Body required must be a boolean.",
            file_path,
        )

    content = request_body.get("content")
    if not isinstance(content, Mapping):
        _add_issue(
            issues,
            f"{path}.content",
            "Request Body content must be a mapping.",
            file_path,
        )
        return
    if not content:
        _add_issue(
            issues,
            f"{path}.content",
            "Request Body content must define at least one media type.",
            file_path,
        )
        return
    for media_type, media in content.items():
        media_path = f"{path}.content.{media_type}"
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


def _add_issue(
    issues: list[ToolError], path: str, message: str, file_path: str
) -> None:
    issues.append(
        ToolError(
            "OPENAPI_REQUEST_BODY_INVALID",
            f"{message} Found at {path}.",
            ExitCode.VALIDATION_ERROR,
            file_path,
        )
    )
