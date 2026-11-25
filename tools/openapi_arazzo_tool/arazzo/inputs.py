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

"""Arazzo 1.1 step input and request body validation."""

from collections.abc import Mapping, Sequence
from typing import Any, TypeGuard

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from ..errors import ExitCode, ToolError
from .model import ArazzoDocument

_PARAMETER_LOCATIONS = frozenset({"path", "query", "header", "cookie"})


def find_input_issues(document: ArazzoDocument) -> list[ToolError]:
    """Validate V1 workflow inputs, step parameters, and request bodies."""
    workflows = document.raw.get("workflows")
    if not _is_sequence(workflows):
        return []

    issues: list[ToolError] = []
    for workflow_index, workflow in enumerate(workflows):
        if not isinstance(workflow, Mapping):
            continue
        workflow_path = f"$.workflows[{workflow_index}]"
        if "inputs" in workflow:
            _validate_workflow_inputs(
                workflow["inputs"], f"{workflow_path}.inputs", document.path, issues
            )
        steps = workflow.get("steps")
        if not _is_sequence(steps):
            continue
        for step_index, step in enumerate(steps):
            if not isinstance(step, Mapping):
                continue
            step_path = f"{workflow_path}.steps[{step_index}]"
            _validate_parameters(
                step.get("parameters"), f"{step_path}.parameters", document.path, issues
            )
            if "requestBody" in step:
                _validate_request_body(
                    step["requestBody"],
                    f"{step_path}.requestBody",
                    document.path,
                    issues,
                )
    return issues


def _validate_workflow_inputs(
    value: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if not isinstance(value, Mapping):
        _add_issue(
            issues, path, "Workflow inputs must be a JSON Schema mapping.", file_path
        )
        return
    try:
        Draft202012Validator.check_schema(value)
    except SchemaError:
        _add_issue(
            issues,
            path,
            "Workflow inputs must be a valid JSON Schema 2020-12 object.",
            file_path,
        )


def _validate_parameters(
    value: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if value is None:
        return
    if not _is_sequence(value):
        _add_issue(issues, path, "Step parameters must be an array.", file_path)
        return

    keys: set[tuple[str, str]] = set()
    for index, parameter in enumerate(value):
        parameter_path = f"{path}[{index}]"
        if not isinstance(parameter, Mapping):
            _add_issue(
                issues, parameter_path, "Step parameter must be a mapping.", file_path
            )
            continue
        if "$ref" in parameter:
            _add_unsupported_issue(
                issues,
                f"{parameter_path}.$ref",
                "Reusable Arazzo parameters",
                file_path,
            )
            continue
        name = parameter.get("name")
        location = parameter.get("in")
        valid_name = isinstance(name, str) and bool(name.strip())
        valid_location = isinstance(location, str) and location in _PARAMETER_LOCATIONS
        if not valid_name:
            _add_issue(
                issues,
                f"{parameter_path}.name",
                "Step parameter name must be a non-empty string.",
                file_path,
            )
        if not valid_location:
            _add_issue(
                issues,
                f"{parameter_path}.in",
                "Step parameter location must be path, query, header, or cookie.",
                file_path,
            )
        if "value" not in parameter:
            _add_issue(
                issues, parameter_path, "Step parameter must define value.", file_path
            )
        if (
            valid_name
            and valid_location
            and isinstance(name, str)
            and isinstance(location, str)
        ):
            key = (name, location)
            if key in keys:
                _add_issue(
                    issues,
                    parameter_path,
                    f"Step parameter '{name}' in '{location}' must be unique.",
                    file_path,
                )
            keys.add(key)


def _validate_request_body(
    value: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if not isinstance(value, Mapping):
        _add_issue(issues, path, "Step requestBody must be a mapping.", file_path)
        return
    content_type = value.get("contentType")
    if not isinstance(content_type, str) or not content_type.strip():
        _add_issue(
            issues,
            f"{path}.contentType",
            "Step requestBody contentType must be a non-empty string.",
            file_path,
        )
    if "payload" not in value:
        _add_issue(issues, path, "Step requestBody must define payload.", file_path)


def _is_sequence(value: Any) -> TypeGuard[Sequence[Any]]:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


def _add_issue(
    issues: list[ToolError], path: str, message: str, file_path: str
) -> None:
    issues.append(
        ToolError(
            "ARAZZO_INPUT_INVALID",
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
