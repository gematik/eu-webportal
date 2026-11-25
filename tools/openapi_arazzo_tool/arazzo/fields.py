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

"""Arazzo 1.1 V1 field allowlist validation."""

from collections.abc import Mapping, Sequence
from typing import Any, TypeGuard

from ..errors import ExitCode, ToolError
from .model import ArazzoDocument

_ROOT_FIELDS = frozenset(
    {"arazzo", "$self", "info", "sourceDescriptions", "workflows", "components"}
)
_INFO_FIELDS = frozenset({"title", "summary", "description", "version"})
_SOURCE_FIELDS = frozenset({"name", "url", "type"})
_WORKFLOW_FIELDS = frozenset(
    {
        "workflowId",
        "summary",
        "description",
        "inputs",
        "dependsOn",
        "steps",
        "successActions",
        "failureActions",
        "outputs",
        "parameters",
    }
)
_STEP_FIELDS = frozenset(
    {
        "description",
        "stepId",
        "operationId",
        "operationPath",
        "operationRef",
        "channelPath",
        "workflowId",
        "parameters",
        "requestBody",
        "successCriteria",
        "onSuccess",
        "onFailure",
        "outputs",
        "timeout",
        "correlationId",
        "action",
        "dependsOn",
    }
)
_PARAMETER_FIELDS = frozenset({"name", "in", "value", "$ref"})
_REQUEST_BODY_FIELDS = frozenset({"contentType", "payload", "replacements"})
_ACTION_FIELDS = frozenset(
    {
        "name",
        "type",
        "workflowId",
        "stepId",
        "parameters",
        "retryAfter",
        "retryLimit",
        "criteria",
        "$ref",
    }
)
_CRITERION_FIELDS = frozenset({"context", "condition", "type"})


def find_field_issues(document: ArazzoDocument) -> list[ToolError]:
    """Reject unknown fields and known V1 fields without supported semantics."""
    raw = document.raw
    issues: list[ToolError] = []
    _validate_fields(raw, _ROOT_FIELDS, "$", document.path, issues)
    _report_unsupported(
        raw, "$self", "$.$self", "Arazzo $self base URIs", document.path, issues
    )

    info = raw.get("info")
    if isinstance(info, Mapping):
        _validate_fields(info, _INFO_FIELDS, "$.info", document.path, issues)

    sources = raw.get("sourceDescriptions")
    if _is_sequence(sources):
        for index, source in enumerate(sources):
            if isinstance(source, Mapping):
                _validate_fields(
                    source,
                    _SOURCE_FIELDS,
                    f"$.sourceDescriptions[{index}]",
                    document.path,
                    issues,
                )

    workflows = raw.get("workflows")
    if _is_sequence(workflows):
        for workflow_index, workflow in enumerate(workflows):
            if isinstance(workflow, Mapping):
                _validate_workflow(workflow, workflow_index, document.path, issues)
    return issues


def _validate_workflow(
    workflow: Mapping[str, Any],
    workflow_index: int,
    file_path: str,
    issues: list[ToolError],
) -> None:
    path = f"$.workflows[{workflow_index}]"
    _validate_fields(workflow, _WORKFLOW_FIELDS, path, file_path, issues)
    steps = workflow.get("steps")
    if not _is_sequence(steps):
        return
    for step_index, step in enumerate(steps):
        if isinstance(step, Mapping):
            _validate_step(step, f"{path}.steps[{step_index}]", file_path, issues)


def _validate_step(
    step: Mapping[str, Any],
    path: str,
    file_path: str,
    issues: list[ToolError],
) -> None:
    _validate_fields(step, _STEP_FIELDS, path, file_path, issues)

    parameters = step.get("parameters")
    if _is_sequence(parameters):
        for index, parameter in enumerate(parameters):
            if isinstance(parameter, Mapping):
                _validate_fields(
                    parameter,
                    _PARAMETER_FIELDS,
                    f"{path}.parameters[{index}]",
                    file_path,
                    issues,
                )

    request_body = step.get("requestBody")
    if isinstance(request_body, Mapping):
        request_body_path = f"{path}.requestBody"
        _validate_fields(
            request_body, _REQUEST_BODY_FIELDS, request_body_path, file_path, issues
        )
        _report_unsupported(
            request_body,
            "replacements",
            f"{request_body_path}.replacements",
            "Request body payload replacements",
            file_path,
            issues,
        )

    _validate_criteria(
        step.get("successCriteria"), f"{path}.successCriteria", file_path, issues
    )
    _validate_actions(step.get("onSuccess"), f"{path}.onSuccess", file_path, issues)
    _validate_actions(step.get("onFailure"), f"{path}.onFailure", file_path, issues)


def _validate_actions(
    value: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if not _is_sequence(value):
        return
    for index, action in enumerate(value):
        if not isinstance(action, Mapping):
            continue
        action_path = f"{path}[{index}]"
        _validate_fields(action, _ACTION_FIELDS, action_path, file_path, issues)
        _validate_criteria(
            action.get("criteria"), f"{action_path}.criteria", file_path, issues
        )


def _validate_criteria(
    value: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if not _is_sequence(value):
        return
    for index, criterion in enumerate(value):
        if isinstance(criterion, Mapping):
            _validate_fields(
                criterion,
                _CRITERION_FIELDS,
                f"{path}[{index}]",
                file_path,
                issues,
            )


def _validate_fields(
    value: Mapping[str, Any],
    allowed_fields: frozenset[str],
    path: str,
    file_path: str,
    issues: list[ToolError],
) -> None:
    for field in value:
        if (
            not isinstance(field, str)
            or field in allowed_fields
            or field.startswith("x-")
        ):
            continue
        issues.append(
            ToolError(
                "ARAZZO_STRUCTURE_INVALID",
                f"Unknown Arazzo field '{field}' found at {path}.{field}.",
                ExitCode.VALIDATION_ERROR,
                file_path,
            )
        )


def _report_unsupported(
    value: Mapping[str, Any],
    field: str,
    path: str,
    feature: str,
    file_path: str,
    issues: list[ToolError],
) -> None:
    if field in value:
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
