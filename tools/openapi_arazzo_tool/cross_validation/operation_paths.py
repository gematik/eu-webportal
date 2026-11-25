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

"""Arazzo operationPath resolution against loaded OpenAPI sources."""

import re
from collections.abc import Mapping, Sequence
from typing import Any, TypeGuard

from ..arazzo.model import ArazzoDocument
from ..errors import ExitCode, ToolError
from ..openapi.refs import resolve_json_pointer
from .sources import ResolvedSources

_OPERATION_PATH = re.compile(r"^\{\$sourceDescriptions\.([A-Za-z0-9_-]+)\.url\}(#/.*)$")
_HTTP_METHODS = frozenset(
    {"delete", "get", "head", "options", "patch", "post", "put", "trace"}
)


def find_operation_path_issues(
    document: ArazzoDocument, resolved_sources: ResolvedSources
) -> list[ToolError]:
    """Resolve V1 OpenAPI operationPath values to actual HTTP operations."""
    workflows = document.raw.get("workflows")
    if not _is_sequence(workflows) or not resolved_sources.sources:
        return []

    issues: list[ToolError] = []
    for workflow_index, workflow in enumerate(workflows):
        if not isinstance(workflow, Mapping) or not _is_sequence(workflow.get("steps")):
            continue
        for step_index, step in enumerate(workflow["steps"]):
            if not isinstance(step, Mapping) or "operationPath" not in step:
                continue
            path = f"$.workflows[{workflow_index}].steps[{step_index}].operationPath"
            _validate_operation_path(
                step.get("operationPath"), path, resolved_sources, document.path, issues
            )
    return issues


def _validate_operation_path(
    value: Any,
    path: str,
    resolved_sources: ResolvedSources,
    file_path: str,
    issues: list[ToolError],
) -> None:
    if not isinstance(value, str) or not value.strip():
        return
    match = _OPERATION_PATH.fullmatch(value)
    if match is None:
        _add_issue(
            issues,
            path,
            "operationPath must use {$sourceDescriptions.<name>.url} followed by an OpenAPI JSON Pointer.",
            file_path,
        )
        return
    source_name, pointer = match.groups()
    source = resolved_sources.sources.get(source_name)
    if source is None:
        _add_issue(
            issues,
            path,
            f"Referenced source '{source_name}' does not exist.",
            file_path,
        )
        return
    if not _is_operation_pointer(pointer):
        _add_issue(
            issues,
            path,
            "operationPath must point to #/paths/<path>/<http-method>.",
            file_path,
        )
        return
    try:
        operation = resolve_json_pointer(
            source.raw, pointer, ref=value, file_label=source.path
        )
    except ToolError:
        _add_issue(
            issues,
            path,
            f"operationPath '{value}' does not resolve in source '{source_name}'.",
            file_path,
        )
        return
    if not isinstance(operation, Mapping):
        _add_issue(
            issues,
            path,
            f"operationPath '{value}' does not resolve to an HTTP operation.",
            file_path,
        )


def _is_operation_pointer(pointer: str) -> bool:
    segments = pointer[2:].split("/") if pointer.startswith("#/") else []
    return (
        len(segments) == 3
        and segments[0] == "paths"
        and segments[2].lower() in _HTTP_METHODS
    )


def _is_sequence(value: Any) -> TypeGuard[Sequence[Any]]:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


def _add_issue(
    issues: list[ToolError], path: str, message: str, file_path: str
) -> None:
    issues.append(
        ToolError(
            "ARAZZO_OPERATION_UNRESOLVED",
            f"{message} Found at {path}.",
            ExitCode.VALIDATION_ERROR,
            file_path,
        )
    )
