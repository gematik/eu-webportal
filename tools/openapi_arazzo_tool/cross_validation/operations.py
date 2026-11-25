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

"""Arazzo operationId resolution against loaded OpenAPI sources."""

import re
from collections.abc import Mapping, Sequence
from typing import Any, TypeGuard

from ..arazzo.model import ArazzoDocument
from ..errors import ExitCode, ToolError
from .sources import ResolvedSources

_SCOPED_OPERATION_ID = re.compile(
    r"^(?:\$sourceDescriptions\.)?([A-Za-z0-9_-]+)\.(.+)$"
)
_HTTP_METHODS = frozenset(
    {"delete", "get", "head", "options", "patch", "post", "put", "trace"}
)


def find_operation_id_issues(
    document: ArazzoDocument, resolved_sources: ResolvedSources
) -> list[ToolError]:
    """Validate all Arazzo ``operationId`` values against OpenAPI sources."""
    workflows = document.raw.get("workflows")
    if not _is_sequence(workflows) or not resolved_sources.sources:
        return []

    source_operation_ids = {
        name: _operation_ids(source.raw)
        for name, source in resolved_sources.sources.items()
    }
    issues: list[ToolError] = []
    for workflow_index, workflow in enumerate(workflows):
        if not isinstance(workflow, Mapping):
            continue
        steps = workflow.get("steps")
        if not _is_sequence(steps):
            continue
        for step_index, step in enumerate(steps):
            if not isinstance(step, Mapping) or "operationId" not in step:
                continue
            path = f"$.workflows[{workflow_index}].steps[{step_index}].operationId"
            _validate_operation_id(
                step.get("operationId"),
                path,
                source_operation_ids,
                document.path,
                issues,
            )
    return issues


def _validate_operation_id(
    value: Any,
    path: str,
    source_operation_ids: dict[str, set[str]],
    file_path: str,
    issues: list[ToolError],
) -> None:
    if not isinstance(value, str) or not value.strip():
        return
    if not value.startswith("$sourceDescriptions.") and len(source_operation_ids) == 1:
        only_operations = next(iter(source_operation_ids.values()))
        if value in only_operations:
            return
    scoped = _SCOPED_OPERATION_ID.fullmatch(value)
    if scoped:
        source_name, operation_id = scoped.groups()
        operations = source_operation_ids.get(source_name)
        if operations is None:
            if not value.startswith("$sourceDescriptions."):
                matches = [
                    name for name, ids in source_operation_ids.items() if value in ids
                ]
                if matches:
                    _add_issue(
                        issues,
                        path,
                        "operationId must use $sourceDescriptions.<name>.<operationId> "
                        "or <source-name>.<operationId> when multiple sources exist.",
                        file_path,
                    )
                    return
            _add_issue(
                issues,
                path,
                f"Referenced source '{source_name}' does not exist.",
                file_path,
            )
        elif operation_id not in operations:
            _add_issue(
                issues,
                path,
                f"operationId '{operation_id}' does not exist in source '{source_name}'.",
                file_path,
            )
        return

    matches = [
        name
        for name, operation_ids in source_operation_ids.items()
        if value in operation_ids
    ]
    if not matches:
        _add_issue(
            issues,
            path,
            f"operationId '{value}' does not exist in any source description.",
            file_path,
        )
    elif len(source_operation_ids) > 1:
        _add_issue(
            issues,
            path,
            "operationId must use $sourceDescriptions.<name>.<operationId> "
            "or <source-name>.<operationId> when multiple sources exist.",
            file_path,
        )


def _operation_ids(document: Mapping[str, Any]) -> set[str]:
    operation_ids: set[str] = set()
    for path_item in _operation_containers(document):
        if not isinstance(path_item, Mapping):
            continue
        for method, operation in path_item.items():
            if method.lower() in _HTTP_METHODS and isinstance(operation, Mapping):
                operation_id = operation.get("operationId")
                if isinstance(operation_id, str) and operation_id:
                    operation_ids.add(operation_id)
    return operation_ids


def _operation_containers(document: Mapping[str, Any]) -> list[Any]:
    containers: list[Any] = []
    for field in ("paths", "webhooks"):
        value = document.get(field)
        if isinstance(value, Mapping):
            containers.extend(value.values())
    return containers


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
