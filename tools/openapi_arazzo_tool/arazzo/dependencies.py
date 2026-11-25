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

"""Arazzo workflow and step dependency validation."""

from collections.abc import Mapping, Sequence
from typing import Any, TypeGuard

from ..errors import ExitCode, ToolError
from .model import ArazzoDocument


def find_dependency_issues(document: ArazzoDocument) -> list[ToolError]:
    """Validate local workflow and sequential step ``dependsOn`` references."""
    workflows = document.raw.get("workflows")
    if not _is_sequence(workflows):
        return []

    workflow_ids = {
        workflow["workflowId"]
        for workflow in workflows
        if isinstance(workflow, Mapping)
        and isinstance(workflow.get("workflowId"), str)
        and workflow["workflowId"]
    }
    issues: list[ToolError] = []
    for workflow_index, workflow in enumerate(workflows):
        if not isinstance(workflow, Mapping):
            continue
        workflow_path = f"$.workflows[{workflow_index}]"
        workflow_id = workflow.get("workflowId")
        _validate_workflow_dependencies(
            workflow.get("dependsOn"),
            f"{workflow_path}.dependsOn",
            workflow_id,
            workflow_ids,
            document.path,
            issues,
        )
        _validate_step_dependencies(
            workflow.get("steps"),
            f"{workflow_path}.steps",
            document.path,
            issues,
        )
    return issues


def _validate_workflow_dependencies(
    value: Any,
    path: str,
    workflow_id: Any,
    workflow_ids: set[str],
    file_path: str,
    issues: list[ToolError],
) -> None:
    if value is None:
        return
    dependencies = _validate_dependency_array(value, path, file_path, issues)
    for index, dependency in enumerate(dependencies):
        dependency_path = f"{path}[{index}]"
        if dependency == workflow_id:
            _add_issue(
                issues,
                dependency_path,
                "Workflow must not depend on itself.",
                file_path,
            )
        elif dependency not in workflow_ids:
            _add_issue(
                issues,
                dependency_path,
                f"Referenced workflow '{dependency}' does not exist.",
                file_path,
            )


def _validate_step_dependencies(
    value: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if not _is_sequence(value):
        return
    known_steps: set[str] = set()
    for index, step in enumerate(value):
        if not isinstance(step, Mapping):
            continue
        step_path = f"{path}[{index}]"
        for dependency_index, dependency in enumerate(
            _validate_dependency_array(
                step.get("dependsOn"), f"{step_path}.dependsOn", file_path, issues
            )
        ):
            dependency_path = f"{step_path}.dependsOn[{dependency_index}]"
            if dependency not in known_steps:
                _add_issue(
                    issues,
                    dependency_path,
                    f"Step dependency '{dependency}' must reference a preceding step.",
                    file_path,
                )
        step_id = step.get("stepId")
        if isinstance(step_id, str) and step_id:
            known_steps.add(step_id)


def _validate_dependency_array(
    value: Any, path: str, file_path: str, issues: list[ToolError]
) -> list[str]:
    if value is None:
        return []
    if not _is_sequence(value):
        _add_issue(issues, path, "dependsOn must be an array.", file_path)
        return []
    dependencies: list[str] = []
    for index, dependency in enumerate(value):
        dependency_path = f"{path}[{index}]"
        if not isinstance(dependency, str) or not dependency.strip():
            _add_issue(
                issues,
                dependency_path,
                "Dependency must be a non-empty string.",
                file_path,
            )
            continue
        if dependency in dependencies:
            _add_issue(
                issues,
                dependency_path,
                f"Dependency '{dependency}' must be unique.",
                file_path,
            )
            continue
        dependencies.append(dependency)
    return dependencies


def _is_sequence(value: Any) -> TypeGuard[Sequence[Any]]:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


def _add_issue(
    issues: list[ToolError], path: str, message: str, file_path: str
) -> None:
    issues.append(
        ToolError(
            "ARAZZO_DEPENDENCY_INVALID",
            f"{message} Found at {path}.",
            ExitCode.VALIDATION_ERROR,
            file_path,
        )
    )
