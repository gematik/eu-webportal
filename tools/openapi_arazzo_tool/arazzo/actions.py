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

"""Arazzo 1.1 onSuccess and onFailure action validation."""

from collections.abc import Mapping, Sequence
from typing import Any, TypeGuard

from ..errors import ExitCode, ToolError
from .model import ArazzoDocument

_SUCCESS_ACTION_TYPES = frozenset({"goto", "end"})
_FAILURE_ACTION_TYPES = frozenset({"goto", "retry", "end"})


def find_action_issues(document: ArazzoDocument) -> list[ToolError]:
    """Validate supported V1 actions and resolve explicit goto targets."""
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
        steps = workflow.get("steps")
        if not _is_sequence(steps):
            continue
        step_ids = {
            step["stepId"]
            for step in steps
            if isinstance(step, Mapping)
            and isinstance(step.get("stepId"), str)
            and step["stepId"]
        }
        for step_index, step in enumerate(steps):
            if not isinstance(step, Mapping):
                continue
            step_path = f"$.workflows[{workflow_index}].steps[{step_index}]"
            _validate_actions(
                step.get("onSuccess"),
                f"{step_path}.onSuccess",
                _SUCCESS_ACTION_TYPES,
                step_ids,
                workflow_ids,
                document.path,
                issues,
            )
            _validate_actions(
                step.get("onFailure"),
                f"{step_path}.onFailure",
                _FAILURE_ACTION_TYPES,
                step_ids,
                workflow_ids,
                document.path,
                issues,
            )
    return issues


def _validate_actions(
    value: Any,
    path: str,
    allowed_types: frozenset[str],
    step_ids: set[str],
    workflow_ids: set[str],
    file_path: str,
    issues: list[ToolError],
) -> None:
    if value is None:
        return
    if not _is_sequence(value):
        _add_issue(issues, path, "Actions must be an array.", file_path)
        return
    names: set[str] = set()
    for index, action in enumerate(value):
        action_path = f"{path}[{index}]"
        if not isinstance(action, Mapping):
            _add_issue(issues, action_path, "Action must be a mapping.", file_path)
            continue
        if "$ref" in action:
            _add_unsupported_issue(
                issues, f"{action_path}.$ref", "Reusable Arazzo actions", file_path
            )
            continue
        if "parameters" in action:
            _add_unsupported_issue(
                issues, f"{action_path}.parameters", "Action parameters", file_path
            )
        name = action.get("name")
        _require_non_empty_string(
            name, f"{action_path}.name", "Action name", file_path, issues
        )
        if isinstance(name, str) and name.strip():
            if name in names:
                _add_issue(
                    issues,
                    f"{action_path}.name",
                    f"Action name '{name}' must be unique.",
                    file_path,
                )
            names.add(name)
        action_type = action.get("type")
        if action_type not in allowed_types:
            supported_types = ", ".join(sorted(allowed_types))
            _add_issue(
                issues,
                f"{action_path}.type",
                f"Action type must be one of {supported_types}.",
                file_path,
            )
            continue
        _validate_criteria(
            action.get("criteria"), f"{action_path}.criteria", file_path, issues
        )
        if action_type == "goto":
            _validate_goto_target(
                action, action_path, step_ids, workflow_ids, file_path, issues
            )
        elif action_type == "retry":
            _validate_retry(
                action, action_path, step_ids, workflow_ids, file_path, issues
            )
        else:
            _validate_end(action, action_path, file_path, issues)


def _validate_criteria(
    value: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if value is None:
        return
    if not _is_sequence(value):
        _add_issue(issues, path, "Action criteria must be an array.", file_path)
        return
    if not value:
        _add_issue(
            issues,
            path,
            "Action criteria must define at least one criterion.",
            file_path,
        )
        return
    for index, criterion in enumerate(value):
        criterion_path = f"{path}[{index}]"
        if not isinstance(criterion, Mapping):
            _add_issue(
                issues, criterion_path, "Action criterion must be a mapping.", file_path
            )
        elif (
            not isinstance(criterion.get("condition"), str)
            or not criterion["condition"].strip()
        ):
            _add_issue(
                issues,
                f"{criterion_path}.condition",
                "Action criterion condition must be a non-empty string.",
                file_path,
            )


def _validate_goto_target(
    action: Mapping[str, Any],
    path: str,
    step_ids: set[str],
    workflow_ids: set[str],
    file_path: str,
    issues: list[ToolError],
) -> None:
    for field in ("retryAfter", "retryLimit"):
        if field in action:
            _add_issue(
                issues,
                f"{path}.{field}",
                f"goto action must not define {field}.",
                file_path,
            )
    has_step_id = "stepId" in action
    has_workflow_id = "workflowId" in action
    if has_step_id == has_workflow_id:
        _add_issue(
            issues,
            path,
            "goto action must define exactly one of stepId or workflowId.",
            file_path,
        )
        return
    if has_step_id:
        _validate_known_target(
            action.get("stepId"), step_ids, f"{path}.stepId", "step", file_path, issues
        )
    else:
        _validate_known_target(
            action.get("workflowId"),
            workflow_ids,
            f"{path}.workflowId",
            "workflow",
            file_path,
            issues,
        )


def _validate_known_target(
    value: Any,
    known_targets: set[str],
    path: str,
    target_type: str,
    file_path: str,
    issues: list[ToolError],
) -> None:
    if not isinstance(value, str) or not value.strip():
        _add_issue(
            issues,
            path,
            f"goto {target_type} target must be a non-empty string.",
            file_path,
        )
    elif value not in known_targets:
        _add_issue(
            issues,
            path,
            f"goto {target_type} target '{value}' does not exist.",
            file_path,
        )


def _validate_retry(
    action: Mapping[str, Any],
    path: str,
    step_ids: set[str],
    workflow_ids: set[str],
    file_path: str,
    issues: list[ToolError],
) -> None:
    retry_after = action.get("retryAfter")
    if retry_after is not None and (
        not isinstance(retry_after, (int, float))
        or isinstance(retry_after, bool)
        or retry_after < 0
    ):
        _add_issue(
            issues,
            f"{path}.retryAfter",
            "retry retryAfter must be a non-negative number.",
            file_path,
        )

    retry_limit = action.get("retryLimit")
    if retry_limit is not None and (
        not isinstance(retry_limit, int)
        or isinstance(retry_limit, bool)
        or retry_limit < 0
    ):
        _add_issue(
            issues,
            f"{path}.retryLimit",
            "retry retryLimit must be a non-negative integer.",
            file_path,
        )

    if "stepId" in action or "workflowId" in action:
        _validate_goto_target(action, path, step_ids, workflow_ids, file_path, issues)


def _validate_end(
    action: Mapping[str, Any], path: str, file_path: str, issues: list[ToolError]
) -> None:
    forbidden = {"stepId", "workflowId", "retryAfter", "retryLimit"} & action.keys()
    for field in sorted(forbidden):
        _add_issue(
            issues, f"{path}.{field}", f"end action must not define {field}.", file_path
        )


def _is_sequence(value: Any) -> TypeGuard[Sequence[Any]]:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


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
            "ARAZZO_ACTION_INVALID",
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
