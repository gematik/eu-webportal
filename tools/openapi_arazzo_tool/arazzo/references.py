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

"""Structural validation for step-output runtime-expression references."""

import re
from collections.abc import Mapping, Sequence
from typing import Any, TypeGuard

from ..errors import ExitCode, ToolError
from .model import ArazzoDocument

_STEP_OUTPUT_REFERENCE = re.compile(
    r"\$steps\.([A-Za-z0-9_-]+)\.outputs\.([A-Za-z0-9._-]+)"
)


def find_step_output_reference_issues(document: ArazzoDocument) -> list[ToolError]:
    """Validate resolvable, non-forward step-output references.

    This intentionally recognizes only the stable ``$steps.<id>.outputs.<name>``
    reference shape. Full runtime-expression parsing remains Milestone 4.
    """
    workflows = document.raw.get("workflows")
    if not _is_sequence(workflows):
        return []

    issues: list[ToolError] = []
    for workflow_index, workflow in enumerate(workflows):
        if not isinstance(workflow, Mapping):
            continue
        workflow_path = f"$.workflows[{workflow_index}]"
        steps = workflow.get("steps")
        if not _is_sequence(steps):
            continue
        output_indexes = _build_output_indexes(steps)
        _validate_values(
            workflow.get("outputs"),
            f"{workflow_path}.outputs",
            len(steps),
            output_indexes,
            document.path,
            issues,
        )
        for step_index, step in enumerate(steps):
            if not isinstance(step, Mapping):
                continue
            step_path = f"{workflow_path}.steps[{step_index}]"
            for value, path in _step_expression_values(step, step_path):
                _validate_values(
                    value,
                    path,
                    step_index,
                    output_indexes,
                    document.path,
                    issues,
                )
    return issues


def _build_output_indexes(steps: Sequence[Any]) -> dict[str, tuple[int, set[str]]]:
    indexes: dict[str, tuple[int, set[str]]] = {}
    for step_index, step in enumerate(steps):
        if not isinstance(step, Mapping):
            continue
        step_id = step.get("stepId")
        outputs = step.get("outputs")
        if not isinstance(step_id, str) or not isinstance(outputs, Mapping):
            continue
        indexes[step_id] = (
            step_index,
            {name for name in outputs if isinstance(name, str)},
        )
    return indexes


def _step_expression_values(
    step: Mapping[str, Any], step_path: str
) -> list[tuple[Any, str]]:
    values: list[tuple[Any, str]] = [
        (step.get("parameters"), f"{step_path}.parameters"),
        (step.get("requestBody"), f"{step_path}.requestBody"),
        (step.get("outputs"), f"{step_path}.outputs"),
        (step.get("successCriteria"), f"{step_path}.successCriteria"),
        (step.get("onSuccess"), f"{step_path}.onSuccess"),
        (step.get("onFailure"), f"{step_path}.onFailure"),
    ]
    return values


def _validate_values(
    value: Any,
    path: str,
    current_step_index: int,
    output_indexes: dict[str, tuple[int, set[str]]],
    file_path: str,
    issues: list[ToolError],
) -> None:
    if isinstance(value, str):
        _validate_string(
            value, path, current_step_index, output_indexes, file_path, issues
        )
    elif isinstance(value, Mapping):
        for key, nested_value in value.items():
            _validate_values(
                nested_value,
                f"{path}.{key}",
                current_step_index,
                output_indexes,
                file_path,
                issues,
            )
    elif _is_sequence(value):
        for index, nested_value in enumerate(value):
            _validate_values(
                nested_value,
                f"{path}[{index}]",
                current_step_index,
                output_indexes,
                file_path,
                issues,
            )


def _validate_string(
    value: str,
    path: str,
    current_step_index: int,
    output_indexes: dict[str, tuple[int, set[str]]],
    file_path: str,
    issues: list[ToolError],
) -> None:
    for match in _STEP_OUTPUT_REFERENCE.finditer(value):
        step_id, output_name = match.groups()
        target = output_indexes.get(step_id)
        if target is None:
            _add_issue(
                issues, path, f"Referenced step '{step_id}' does not exist.", file_path
            )
            continue
        target_index, output_names = target
        if target_index >= current_step_index:
            _add_issue(
                issues,
                path,
                f"Reference to output '{output_name}' of step '{step_id}' is a forward reference.",
                file_path,
            )
        elif output_name not in output_names:
            _add_issue(
                issues,
                path,
                f"Referenced output '{output_name}' does not exist on step '{step_id}'.",
                file_path,
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
            "ARAZZO_EXPRESSION_UNRESOLVED",
            f"{message} Found at {path}.",
            ExitCode.VALIDATION_ERROR,
            file_path,
        )
    )
