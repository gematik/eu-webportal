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

"""Semantic cross-validation of Arazzo workflow runtime-expression references."""

import re
from collections.abc import Mapping, Sequence
from typing import Any, TypeGuard

from ..arazzo.model import ArazzoDocument
from ..arazzo.runtime_expressions import parse_runtime_expressions
from ..errors import ExitCode, ToolError

_INPUT = re.compile(r"^\$inputs\.([^#]+)(?:#.*)?$")
_OUTPUT = re.compile(r"^\$outputs\.([^#]+)(?:#.*)?$")
_WORKFLOW = re.compile(
    r"^\$workflows\.([A-Za-z0-9_-]+)\.(inputs|outputs)\.([^#]+)(?:#.*)?$"
)


def find_expression_dependency_issues(document: ArazzoDocument) -> list[ToolError]:
    """Resolve workflow input/output references after syntax validation."""
    workflows = document.raw.get("workflows")
    if not _is_sequence(workflows):
        return []

    workflow_symbols = _workflow_symbols(workflows)
    issues: list[ToolError] = []
    for workflow_index, workflow in enumerate(workflows):
        if not isinstance(workflow, Mapping):
            continue
        workflow_path = f"$.workflows[{workflow_index}]"
        workflow_id = workflow.get("workflowId")
        current = (
            workflow_symbols.get(workflow_id, (set(), set()))
            if isinstance(workflow_id, str)
            else (set(), set())
        )
        _validate_value(
            workflow.get("outputs"),
            f"{workflow_path}.outputs",
            current,
            workflow_symbols,
            document.path,
            issues,
        )
        steps = workflow.get("steps")
        if not _is_sequence(steps):
            continue
        for step_index, step in enumerate(steps):
            if not isinstance(step, Mapping):
                continue
            step_path = f"{workflow_path}.steps[{step_index}]"
            for field in (
                "parameters",
                "requestBody",
                "outputs",
                "successCriteria",
                "onSuccess",
                "onFailure",
            ):
                _validate_value(
                    step.get(field),
                    f"{step_path}.{field}",
                    current,
                    workflow_symbols,
                    document.path,
                    issues,
                )
    return issues


def _workflow_symbols(
    workflows: Sequence[Any],
) -> dict[str, tuple[set[str], set[str]]]:
    symbols: dict[str, tuple[set[str], set[str]]] = {}
    for workflow in workflows:
        if not isinstance(workflow, Mapping):
            continue
        workflow_id = workflow.get("workflowId")
        if not isinstance(workflow_id, str):
            continue
        inputs = workflow.get("inputs")
        properties = inputs.get("properties") if isinstance(inputs, Mapping) else None
        outputs = workflow.get("outputs")
        symbols[workflow_id] = (
            {name for name in properties if isinstance(name, str)}
            if isinstance(properties, Mapping)
            else set(),
            {name for name in outputs if isinstance(name, str)}
            if isinstance(outputs, Mapping)
            else set(),
        )
    return symbols


def _validate_value(
    value: Any,
    path: str,
    current_symbols: tuple[set[str], set[str]],
    workflow_symbols: dict[str, tuple[set[str], set[str]]],
    file_path: str,
    issues: list[ToolError],
) -> None:
    if isinstance(value, str):
        _validate_string(
            value, path, current_symbols, workflow_symbols, file_path, issues
        )
    elif isinstance(value, Mapping):
        for key, nested in value.items():
            _validate_value(
                nested,
                f"{path}.{key}",
                current_symbols,
                workflow_symbols,
                file_path,
                issues,
            )
    elif _is_sequence(value):
        for index, nested in enumerate(value):
            _validate_value(
                nested,
                f"{path}[{index}]",
                current_symbols,
                workflow_symbols,
                file_path,
                issues,
            )


def _validate_string(
    value: str,
    path: str,
    current_symbols: tuple[set[str], set[str]],
    workflow_symbols: dict[str, tuple[set[str], set[str]]],
    file_path: str,
    issues: list[ToolError],
) -> None:
    try:
        expressions = parse_runtime_expressions(value)
    except ValueError:
        return
    for parsed in expressions:
        expression = parsed.value
        if match := _INPUT.fullmatch(expression):
            _require_symbol(
                match.group(1),
                current_symbols[0],
                "workflow input",
                path,
                file_path,
                issues,
            )
        elif match := _OUTPUT.fullmatch(expression):
            _require_symbol(
                match.group(1),
                current_symbols[1],
                "workflow output",
                path,
                file_path,
                issues,
            )
        elif match := _WORKFLOW.fullmatch(expression):
            workflow_id, field, name = match.groups()
            target = workflow_symbols.get(workflow_id)
            if target is None:
                _add_issue(
                    issues,
                    path,
                    f"Referenced workflow '{workflow_id}' does not exist.",
                    file_path,
                )
                continue
            symbols = target[0] if field == "inputs" else target[1]
            _require_symbol(
                name, symbols, f"workflow {field[:-1]}", path, file_path, issues
            )


def _require_symbol(
    name: str,
    symbols: set[str],
    label: str,
    path: str,
    file_path: str,
    issues: list[ToolError],
) -> None:
    if name not in symbols:
        _add_issue(
            issues, path, f"Referenced {label} '{name}' is not defined.", file_path
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
