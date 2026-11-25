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

"""Cross-validation of Arazzo response references against OpenAPI operations."""

import re
from collections.abc import Iterator, Mapping, Sequence
from typing import Any, TypeGuard

from ..arazzo.model import ArazzoDocument
from ..errors import ExitCode, ToolError
from .parameters import _resolve_operation
from .sources import ResolvedSources

_STATUS_EXPRESSION = re.compile(r"\$statusCode\s*==\s*(\d{3})")
_HEADER_EXPRESSION = re.compile(r"\$response\.header\.([!#$%&'*+\-.^_`|~A-Za-z0-9]+)")
_BODY_EXPRESSION = re.compile(r"\$response\.body#(/[^\s'\"),]*)")


def find_response_reference_issues(
    document: ArazzoDocument,
    sources: ResolvedSources,
) -> list[ToolError]:
    """Validate statically resolvable response status, header, and body references."""
    workflows = document.raw.get("workflows")
    if not _is_sequence(workflows) or not sources.sources:
        return []

    issues: list[ToolError] = []
    for workflow_index, workflow in enumerate(workflows):
        if not isinstance(workflow, Mapping) or not _is_sequence(workflow.get("steps")):
            continue
        for step_index, step in enumerate(workflow["steps"]):
            if not isinstance(step, Mapping):
                continue
            target = _resolve_operation(step, sources)
            if target is None:
                continue
            path = f"$.workflows[{workflow_index}].steps[{step_index}]"
            _validate_step_references(step, target[1], path, document.path, issues)
    return issues


def _validate_step_references(
    step: Mapping[str, Any],
    operation: Mapping[str, Any],
    path: str,
    file_path: str,
    issues: list[ToolError],
) -> None:
    responses = operation.get("responses")
    if not isinstance(responses, Mapping):
        return

    success_statuses = _status_references(step.get("successCriteria"))
    _validate_expressions(
        step.get("successCriteria"),
        responses,
        None,
        f"{path}.successCriteria",
        file_path,
        issues,
    )
    _validate_expressions(
        step.get("onSuccess"), responses, None, f"{path}.onSuccess", file_path, issues
    )
    _validate_expressions(
        step.get("onFailure"), responses, None, f"{path}.onFailure", file_path, issues
    )
    _validate_expressions(
        step.get("outputs"),
        responses,
        success_statuses or None,
        f"{path}.outputs",
        file_path,
        issues,
    )


def _validate_expressions(
    value: Any,
    responses: Mapping[str, Any],
    preferred_statuses: set[str] | None,
    path: str,
    file_path: str,
    issues: list[ToolError],
) -> None:
    for expression_path, expression in _iter_strings(value, path):
        referenced_statuses = set(_STATUS_EXPRESSION.findall(expression))
        for status in referenced_statuses:
            if _find_response(responses, status) is None:
                _add_issue(
                    issues,
                    expression_path,
                    f"Response status code '{status}' is not defined by the target operation.",
                    file_path,
                )

        candidate_statuses = referenced_statuses or preferred_statuses
        candidates = _candidate_responses(responses, candidate_statuses)
        for header in _HEADER_EXPRESSION.findall(expression):
            if candidates and not any(
                _has_header(response, header) for response in candidates
            ):
                _add_issue(
                    issues,
                    expression_path,
                    f"Response header '{header}' is not defined for the referenced response.",
                    file_path,
                )
        for pointer in _BODY_EXPRESSION.findall(expression):
            if candidates and not any(
                _supports_body_pointer(response, pointer) for response in candidates
            ):
                _add_issue(
                    issues,
                    expression_path,
                    f"Response body path '#{pointer}' is not defined by the referenced response schema.",
                    file_path,
                )


def _status_references(value: Any) -> set[str]:
    return {
        status
        for _, expression in _iter_strings(value, "$")
        for status in _STATUS_EXPRESSION.findall(expression)
    }


def _candidate_responses(
    responses: Mapping[str, Any],
    statuses: set[str] | None,
) -> list[Mapping[str, Any]]:
    if statuses:
        return [
            response
            for status in statuses
            if isinstance((response := _find_response(responses, status)), Mapping)
        ]
    return [
        response for response in responses.values() if isinstance(response, Mapping)
    ]


def _find_response(
    responses: Mapping[str, Any], status: str
) -> Mapping[str, Any] | None:
    response = responses.get(status)
    if not isinstance(response, Mapping):
        response = responses.get(f"{status[0]}XX") or responses.get(f"{status[0]}xx")
    if not isinstance(response, Mapping):
        response = responses.get("default")
    return response if isinstance(response, Mapping) else None


def _has_header(response: Mapping[str, Any], header: str) -> bool:
    headers = response.get("headers")
    return isinstance(headers, Mapping) and header.lower() in {
        name.lower() for name in headers if isinstance(name, str)
    }


def _supports_body_pointer(response: Mapping[str, Any], pointer: str) -> bool:
    content = response.get("content")
    if not isinstance(content, Mapping):
        return False
    schemas: list[Mapping[str, Any]] = []
    for media in content.values():
        if not isinstance(media, Mapping):
            continue
        schema = media.get("schema")
        if isinstance(schema, Mapping):
            schemas.append(schema)
    return any(_schema_supports_pointer(schema, pointer) for schema in schemas)


def _schema_supports_pointer(schema: Mapping[str, Any], pointer: str) -> bool:
    current: Any = schema
    for raw_token in pointer[1:].split("/"):
        if not isinstance(current, Mapping):
            return False
        if "$ref" in current:
            return True
        token = raw_token.replace("~1", "/").replace("~0", "~")
        properties = current.get("properties")
        if isinstance(properties, Mapping) and token in properties:
            current = properties[token]
            continue
        if token.isdigit() and isinstance(current.get("items"), Mapping):
            current = current["items"]
            continue
        return False
    return True


def _iter_strings(value: Any, path: str) -> Iterator[tuple[str, str]]:
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, Mapping):
        for key, nested in value.items():
            yield from _iter_strings(nested, f"{path}.{key}")
    elif _is_sequence(value):
        for index, nested in enumerate(value):
            yield from _iter_strings(nested, f"{path}[{index}]")


def _is_sequence(value: Any) -> TypeGuard[Sequence[Any]]:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


def _add_issue(
    issues: list[ToolError], path: str, message: str, file_path: str
) -> None:
    issues.append(
        ToolError(
            "ARAZZO_RESPONSE_REFERENCE_INVALID",
            f"{message} Found at {path}.",
            ExitCode.VALIDATION_ERROR,
            file_path,
        )
    )
