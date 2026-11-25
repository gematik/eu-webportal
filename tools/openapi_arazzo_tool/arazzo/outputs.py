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

"""Arazzo 1.1 outputs and success-criteria validation."""

import re
from collections.abc import Mapping, Sequence
from typing import Any, TypeGuard

from ..errors import ExitCode, ToolError
from .model import ArazzoDocument

_OUTPUT_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")


def find_output_issues(document: ArazzoDocument) -> list[ToolError]:
    """Validate output mappings and success criteria before expression parsing."""
    workflows = document.raw.get("workflows")
    if not _is_sequence(workflows):
        return []

    issues: list[ToolError] = []
    for workflow_index, workflow in enumerate(workflows):
        if not isinstance(workflow, Mapping):
            continue
        workflow_path = f"$.workflows[{workflow_index}]"
        _validate_outputs(
            workflow.get("outputs"), f"{workflow_path}.outputs", document.path, issues
        )
        steps = workflow.get("steps")
        if not _is_sequence(steps):
            continue
        for step_index, step in enumerate(steps):
            if not isinstance(step, Mapping):
                continue
            step_path = f"{workflow_path}.steps[{step_index}]"
            _validate_outputs(
                step.get("outputs"), f"{step_path}.outputs", document.path, issues
            )
            _validate_success_criteria(
                step.get("successCriteria"),
                f"{step_path}.successCriteria",
                document.path,
                issues,
            )
    return issues


def _validate_outputs(
    value: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if value is None:
        return
    if not isinstance(value, Mapping):
        _add_issue(issues, path, "Outputs must be a mapping.", file_path)
        return
    for name, expression in value.items():
        output_path = f"{path}.{name}"
        if not isinstance(name, str) or not name.strip():
            _add_issue(
                issues,
                output_path,
                "Output names must be non-empty strings.",
                file_path,
            )
        elif not _OUTPUT_NAME_PATTERN.fullmatch(name):
            _add_issue(
                issues,
                output_path,
                "Output names may contain only letters, digits, periods, hyphens, and underscores.",
                file_path,
            )
        if isinstance(expression, Mapping):
            _add_unsupported_issue(
                issues, output_path, "Arazzo selector objects", file_path
            )
            continue
        if not isinstance(expression, str) or not expression.strip():
            _add_issue(
                issues,
                output_path,
                "Output expressions must be non-empty strings.",
                file_path,
            )


def _validate_success_criteria(
    value: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if value is None:
        return
    if not _is_sequence(value):
        _add_issue(issues, path, "successCriteria must be an array.", file_path)
        return
    if not value:
        _add_issue(
            issues,
            path,
            "successCriteria must define at least one criterion.",
            file_path,
        )
        return
    for index, criterion in enumerate(value):
        criterion_path = f"{path}[{index}]"
        if not isinstance(criterion, Mapping):
            _add_issue(
                issues,
                criterion_path,
                "Success criterion must be a mapping.",
                file_path,
            )
            continue
        condition = criterion.get("condition")
        if not isinstance(condition, str) or not condition.strip():
            _add_issue(
                issues,
                f"{criterion_path}.condition",
                "Success criterion condition must be a non-empty string.",
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
            "ARAZZO_OUTPUT_INVALID",
            f"{message} Found at {path}.",
            ExitCode.VALIDATION_ERROR,
            file_path,
        )
    )


def _add_unsupported_issue(
    issues: list[ToolError], path: str, feature: str, file_path: str
) -> None:
    issues.append(
        ToolError(
            "ARAZZO_FEATURE_UNSUPPORTED",
            f"{feature} are not supported in V1. Found at {path}.",
            ExitCode.VALIDATION_ERROR,
            file_path,
        )
    )
