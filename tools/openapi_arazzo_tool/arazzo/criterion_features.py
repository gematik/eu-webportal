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

"""V1 support-matrix enforcement for Arazzo Criterion Objects."""

from collections.abc import Mapping, Sequence
from typing import Any, TypeGuard

from ..errors import ExitCode, ToolError
from .model import ArazzoDocument

_KNOWN_UNSUPPORTED_TYPES = frozenset({"regex", "jsonpath", "xpath"})


def find_criterion_feature_issues(document: ArazzoDocument) -> list[ToolError]:
    """Reject criterion semantics outside the explicit V1 support matrix."""
    workflows = document.raw.get("workflows")
    if not _is_sequence(workflows):
        return []

    issues: list[ToolError] = []
    for workflow_index, workflow in enumerate(workflows):
        if not isinstance(workflow, Mapping) or not _is_sequence(workflow.get("steps")):
            continue
        for step_index, step in enumerate(workflow["steps"]):
            if not isinstance(step, Mapping):
                continue
            path = f"$.workflows[{workflow_index}].steps[{step_index}]"
            _validate_criteria(
                step.get("successCriteria"),
                f"{path}.successCriteria",
                document.path,
                issues,
            )
            _validate_actions(
                step.get("onSuccess"), f"{path}.onSuccess", document.path, issues
            )
            _validate_actions(
                step.get("onFailure"), f"{path}.onFailure", document.path, issues
            )
    return issues


def _validate_actions(
    value: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if not _is_sequence(value):
        return
    for index, action in enumerate(value):
        if isinstance(action, Mapping):
            _validate_criteria(
                action.get("criteria"),
                f"{path}[{index}].criteria",
                file_path,
                issues,
            )


def _validate_criteria(
    value: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if not _is_sequence(value):
        return
    for index, criterion in enumerate(value):
        if not isinstance(criterion, Mapping):
            continue
        criterion_path = f"{path}[{index}]"
        criterion_type = criterion.get("type")
        if isinstance(criterion_type, Mapping):
            _add_unsupported(
                issues,
                f"{criterion_path}.type",
                "Criterion Expression Type Objects",
                file_path,
            )
        elif criterion_type in _KNOWN_UNSUPPORTED_TYPES:
            _add_unsupported(
                issues,
                f"{criterion_path}.type",
                f"Criterion type '{criterion_type}'",
                file_path,
            )
        elif criterion_type not in (None, "simple"):
            issues.append(
                ToolError(
                    "ARAZZO_CRITERION_INVALID",
                    f"Unknown Criterion type '{criterion_type}'. Found at {criterion_path}.type.",
                    ExitCode.VALIDATION_ERROR,
                    file_path,
                )
            )
        if "context" in criterion:
            _add_unsupported(
                issues,
                f"{criterion_path}.context",
                "Criterion context expressions",
                file_path,
            )


def _add_unsupported(
    issues: list[ToolError],
    path: str,
    feature: str,
    file_path: str,
) -> None:
    issues.append(
        ToolError(
            "ARAZZO_FEATURE_UNSUPPORTED",
            f"{feature} are not supported in V1. Found at {path}.",
            ExitCode.VALIDATION_ERROR,
            file_path,
        )
    )


def _is_sequence(value: Any) -> TypeGuard[Sequence[Any]]:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )
