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

"""Arazzo 1.1 workflow and step identity validation."""

from collections.abc import Mapping, Sequence
from typing import Any, TypeGuard

from ..errors import ExitCode, ToolError
from .model import ArazzoDocument


def find_workflow_issues(document: ArazzoDocument) -> list[ToolError]:
    """Validate workflow IDs, step IDs, and V1 operation selectors."""
    workflows = document.raw.get("workflows")
    if not _is_sequence(workflows):
        return []

    issues: list[ToolError] = []
    workflow_ids: set[str] = set()
    for index, workflow in enumerate(workflows):
        workflow_path = f"$.workflows[{index}]"
        if not isinstance(workflow, Mapping):
            _add_issue(
                issues, workflow_path, "Workflow must be a mapping.", document.path
            )
            continue
        workflow_id = workflow.get("workflowId")
        _validate_unique_identifier(
            workflow_id,
            workflow_ids,
            f"{workflow_path}.workflowId",
            "Workflow",
            document.path,
            issues,
        )
        _report_unsupported_workflow_features(
            workflow, workflow_path, document.path, issues
        )
        _validate_steps(
            workflow.get("steps"), f"{workflow_path}.steps", document.path, issues
        )
    return issues


def _validate_steps(
    value: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if not _is_sequence(value):
        _add_issue(issues, path, "Workflow steps must be an array.", file_path)
        return
    if not value:
        _add_issue(
            issues, path, "Workflow steps must define at least one step.", file_path
        )
        return

    step_ids: set[str] = set()
    for index, step in enumerate(value):
        step_path = f"{path}[{index}]"
        if not isinstance(step, Mapping):
            _add_issue(issues, step_path, "Step must be a mapping.", file_path)
            continue
        _validate_unique_identifier(
            step.get("stepId"),
            step_ids,
            f"{step_path}.stepId",
            "Step",
            file_path,
            issues,
        )
        _validate_operation_selector(step, step_path, file_path, issues)
        _validate_timeout(
            step.get("timeout"), f"{step_path}.timeout", file_path, issues
        )


def _validate_unique_identifier(
    value: Any,
    known_values: set[str],
    path: str,
    label: str,
    file_path: str,
    issues: list[ToolError],
) -> None:
    if not isinstance(value, str) or not value.strip():
        _add_issue(issues, path, f"{label} ID must be a non-empty string.", file_path)
        return
    if value in known_values:
        _add_issue(issues, path, f"{label} ID '{value}' must be unique.", file_path)
        return
    known_values.add(value)


def _validate_operation_selector(
    step: Mapping[str, Any], path: str, file_path: str, issues: list[ToolError]
) -> None:
    _report_unsupported_step_features(step, path, file_path, issues)

    has_operation_id = "operationId" in step
    has_operation_path = "operationPath" in step
    if has_operation_id == has_operation_path:
        _add_issue(
            issues,
            path,
            "Step must define exactly one of operationId or operationPath.",
            file_path,
        )
        return
    field = "operationId" if has_operation_id else "operationPath"
    value = step[field]
    if not isinstance(value, str) or not value.strip():
        _add_issue(
            issues, f"{path}.{field}", f"{field} must be a non-empty string.", file_path
        )


def _report_unsupported_step_features(
    step: Mapping[str, Any], path: str, file_path: str, issues: list[ToolError]
) -> None:
    unsupported_features = {
        "operationRef": "operationRef",
        "channelPath": "AsyncAPI channelPath references",
        "action": "AsyncAPI step actions",
        "workflowId": "workflow invocation steps",
        "correlationId": "AsyncAPI correlation identifiers",
    }
    for field, feature in unsupported_features.items():
        if field in step:
            issues.append(
                ToolError(
                    "ARAZZO_FEATURE_UNSUPPORTED",
                    f"{feature} is not supported in V1. Found at {path}.{field}.",
                    ExitCode.VALIDATION_ERROR,
                    file_path,
                )
            )


def _validate_timeout(
    value: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if value is None:
        return
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        _add_issue(
            issues,
            path,
            "Step timeout must be a non-negative integer in milliseconds.",
            file_path,
        )


def _report_unsupported_workflow_features(
    workflow: Mapping[str, Any], path: str, file_path: str, issues: list[ToolError]
) -> None:
    unsupported_features = {
        "parameters": "Workflow-level parameters",
        "successActions": "Workflow-level success actions",
        "failureActions": "Workflow-level failure actions",
    }
    for field, feature in unsupported_features.items():
        if field in workflow:
            issues.append(
                ToolError(
                    "ARAZZO_FEATURE_UNSUPPORTED",
                    f"{feature} are not supported in V1. Found at {path}.{field}.",
                    ExitCode.VALIDATION_ERROR,
                    file_path,
                )
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
            "ARAZZO_WORKFLOW_INVALID",
            f"{message} Found at {path}.",
            ExitCode.VALIDATION_ERROR,
            file_path,
        )
    )
