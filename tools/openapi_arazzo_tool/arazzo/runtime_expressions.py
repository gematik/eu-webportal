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

"""Strict, non-evaluating parser for Arazzo 1.1 runtime expressions."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, TypeGuard

from ..errors import ExitCode, ToolError
from .model import ArazzoDocument

_IDENTIFIER = r"[A-Za-z0-9._-]+"
_STRICT_IDENTIFIER = r"[A-Za-z0-9_-]+"
_HEADER_TOKEN = r"[!#$%&'*+\-.^_`|~A-Za-z0-9]+"
_POINTER = r"(?:#(?:/(?:[^/{}~\s]|~[01])*)*)?"
_EXPRESSION_PATTERNS = (
    re.compile(r"^\$(?:url|method|statusCode|self)$"),
    re.compile(rf"^\$(?:inputs|outputs)\.{_IDENTIFIER}{_POINTER}$"),
    re.compile(rf"^\$steps\.{_STRICT_IDENTIFIER}\.outputs\.{_IDENTIFIER}{_POINTER}$"),
    re.compile(
        rf"^\$workflows\.{_STRICT_IDENTIFIER}\.(?:inputs|outputs)\.{_IDENTIFIER}{_POINTER}$"
    ),
    re.compile(rf"^\$(?:request|response|message)\.header\.{_HEADER_TOKEN}$"),
    re.compile(r"^\$request\.(?:query|path)\..+$"),
    re.compile(rf"^\$(?:request|response)\.body{_POINTER}$"),
    re.compile(rf"^\$message\.payload{_POINTER}$"),
    re.compile(rf"^\$sourceDescriptions\.{_STRICT_IDENTIFIER}\..+$"),
    re.compile(
        rf"^\$components\.(?:parameters|successActions|failureActions)\.{_IDENTIFIER}$"
    ),
)
_DIRECT_END = frozenset(" \t\r\n'\"(),<>=!&")


@dataclass(frozen=True)
class RuntimeExpression:
    """A syntactically validated runtime expression."""

    value: str
    start: int
    end: int
    embedded: bool


def parse_runtime_expressions(value: str) -> list[RuntimeExpression]:
    """Parse every runtime expression without evaluating arbitrary content."""
    expressions: list[RuntimeExpression] = []
    index = 0
    while index < len(value):
        marker = value.find("$", index)
        if marker < 0:
            break
        if marker + 1 >= len(value) or not value[marker + 1].isalpha():
            index = marker + 1
            continue
        embedded = marker > 0 and value[marker - 1] == "{"
        if embedded:
            closing = value.find("}", marker + 1)
            if closing < 0:
                raise ValueError("Embedded runtime expression is missing closing '}'.")
            expression = value[marker:closing]
            end = closing + 1
        else:
            end = marker + 1
            while (
                end < len(value) and value[end] not in _DIRECT_END and value[end] != "}"
            ):
                end += 1
            expression = value[marker:end]
        if not any(pattern.fullmatch(expression) for pattern in _EXPRESSION_PATTERNS):
            raise ValueError(
                f"Invalid or unsupported runtime expression '{expression}'."
            )
        expressions.append(RuntimeExpression(expression, marker, end, embedded))
        index = end
    return expressions


def find_runtime_expression_issues(document: ArazzoDocument) -> list[ToolError]:
    """Validate runtime-expression syntax in all V1 expression-bearing fields."""
    workflows = document.raw.get("workflows")
    if not _is_sequence(workflows):
        return []

    issues: list[ToolError] = []
    for workflow_index, workflow in enumerate(workflows):
        if not isinstance(workflow, Mapping):
            continue
        workflow_path = f"$.workflows[{workflow_index}]"
        _validate_value(
            workflow.get("outputs"), f"{workflow_path}.outputs", document.path, issues
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
                    step.get(field), f"{step_path}.{field}", document.path, issues
                )
    return issues


def _validate_value(
    value: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if isinstance(value, str):
        try:
            parse_runtime_expressions(value)
        except ValueError as error:
            issues.append(
                ToolError(
                    "ARAZZO_EXPRESSION_INVALID",
                    f"{error} Found at {path}.",
                    ExitCode.VALIDATION_ERROR,
                    file_path,
                )
            )
    elif isinstance(value, Mapping):
        for key, nested in value.items():
            _validate_value(nested, f"{path}.{key}", file_path, issues)
    elif _is_sequence(value):
        for index, nested in enumerate(value):
            _validate_value(nested, f"{path}[{index}]", file_path, issues)


def _is_sequence(value: Any) -> TypeGuard[Sequence[Any]]:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )
