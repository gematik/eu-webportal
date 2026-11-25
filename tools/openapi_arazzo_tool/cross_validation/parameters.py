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

"""Arazzo step parameter validation against resolved OpenAPI operations."""

import re
from collections.abc import Mapping, Sequence
from typing import Any, TypeGuard

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from ..arazzo.model import ArazzoDocument
from ..errors import ExitCode, ToolError
from ..openapi.refs import resolve_json_pointer
from .sources import ResolvedSources

_HTTP_METHODS = frozenset(
    {"delete", "get", "head", "options", "patch", "post", "put", "trace"}
)
_SCOPED_OPERATION_ID = re.compile(
    r"^(?:\$sourceDescriptions\.)?([A-Za-z0-9_-]+)\.(.+)$"
)
_OPERATION_PATH = re.compile(r"^\{\$sourceDescriptions\.([A-Za-z0-9_-]+)\.url\}(#/.*)$")


def find_parameter_issues(
    document: ArazzoDocument, resolved_sources: ResolvedSources
) -> list[ToolError]:
    """Check Arazzo parameters against target OpenAPI parameter definitions."""
    workflows = document.raw.get("workflows")
    if not _is_sequence(workflows) or not resolved_sources.sources:
        return []

    issues: list[ToolError] = []
    for workflow_index, workflow in enumerate(workflows):
        if not isinstance(workflow, Mapping) or not _is_sequence(workflow.get("steps")):
            continue
        for step_index, step in enumerate(workflow["steps"]):
            if not isinstance(step, Mapping):
                continue
            operation = _resolve_operation(step, resolved_sources)
            if operation is None:
                continue
            path = f"$.workflows[{workflow_index}].steps[{step_index}]"
            _validate_step_parameters(
                step.get("parameters"), operation, path, document.path, issues
            )
    return issues


def _resolve_operation(
    step: Mapping[str, Any], sources: ResolvedSources
) -> tuple[Mapping[str, Any], Mapping[str, Any]] | None:
    resolved = _resolve_operation_with_source(step, sources)
    return resolved[1:] if resolved is not None else None


def _resolve_operation_with_source(
    step: Mapping[str, Any],
    sources: ResolvedSources,
) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]] | None:
    if isinstance(step.get("operationId"), str):
        return _resolve_operation_id_with_source(step["operationId"], sources)
    if isinstance(step.get("operationPath"), str):
        return _resolve_operation_path_with_source(step["operationPath"], sources)
    return None


def _resolve_operation_id_with_source(
    value: str,
    sources: ResolvedSources,
) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]] | None:
    for source in sources.sources.values():
        operation = _find_operation_id(source.raw, value)
        if len(sources.sources) == 1 and operation is not None:
            return source.raw, *operation

    scoped = _SCOPED_OPERATION_ID.fullmatch(value)
    if scoped:
        source = sources.sources.get(scoped.group(1))
        if source is not None:
            operation = _find_operation_id(source.raw, scoped.group(2))
            return (source.raw, *operation) if operation is not None else None
    return None


def _resolve_operation_id(
    value: str, sources: ResolvedSources
) -> tuple[Mapping[str, Any], Mapping[str, Any]] | None:
    if not value.startswith("$sourceDescriptions.") and len(sources.sources) == 1:
        source = next(iter(sources.sources.values()))
        exact = _find_operation_id(source.raw, value)
        if exact is not None:
            return exact
    scoped = _SCOPED_OPERATION_ID.fullmatch(value)
    if scoped:
        source = sources.sources.get(scoped.group(1))
        if source is not None:
            return _find_operation_id(source.raw, scoped.group(2))
        if not value.startswith("$sourceDescriptions.") and len(sources.sources) == 1:
            source = next(iter(sources.sources.values()))
            return _find_operation_id(source.raw, value)
        return None
    if len(sources.sources) != 1:
        return None
    source = next(iter(sources.sources.values()))
    return _find_operation_id(source.raw, value)


def _find_operation_id(
    document: Mapping[str, Any], operation_id: str
) -> tuple[Mapping[str, Any], Mapping[str, Any]] | None:
    containers: list[Any] = []
    for field in ("paths", "webhooks"):
        value = document.get(field)
        if isinstance(value, Mapping):
            containers.extend(value.values())
    for path_item in containers:
        if not isinstance(path_item, Mapping):
            continue
        for method, operation in path_item.items():
            if (
                method.lower() in _HTTP_METHODS
                and isinstance(operation, Mapping)
                and operation.get("operationId") == operation_id
            ):
                return path_item, operation
    return None


def _resolve_operation_path(
    value: str, sources: ResolvedSources
) -> tuple[Mapping[str, Any], Mapping[str, Any]] | None:
    resolved = _resolve_operation_path_with_source(value, sources)
    return resolved[1:] if resolved is not None else None


def _resolve_operation_path_with_source(
    value: str,
    sources: ResolvedSources,
) -> tuple[Mapping[str, Any], Mapping[str, Any], Mapping[str, Any]] | None:
    match = _OPERATION_PATH.fullmatch(value)
    if match is None:
        return None
    source = sources.sources.get(match.group(1))
    if source is None:
        return None
    try:
        operation = resolve_json_pointer(
            source.raw, match.group(2), ref=value, file_label=source.path
        )
    except ToolError:
        return None
    segments = match.group(2)[2:].split("/")
    if len(segments) != 3:
        return None
    path_item = source.raw.get("paths", {}).get(
        segments[1].replace("~1", "/").replace("~0", "~")
    )
    if not isinstance(path_item, Mapping) or not isinstance(operation, Mapping):
        return None
    return source.raw, path_item, operation


def _validate_step_parameters(
    value: Any,
    target: tuple[Mapping[str, Any], Mapping[str, Any]],
    path: str,
    file_path: str,
    issues: list[ToolError],
) -> None:
    if value is None:
        supplied: dict[tuple[str, str], Mapping[str, Any]] = {}
    elif not _is_sequence(value):
        return
    else:
        supplied = {
            (
                parameter["name"],
                parameter["in"].lower()
                if parameter["in"] != "header"
                else parameter["in"],
            ): parameter
            for parameter in value
            if isinstance(parameter, Mapping)
            and isinstance(parameter.get("name"), str)
            and isinstance(parameter.get("in"), str)
        }

    defined = _effective_parameters(*target)
    for key, parameter in supplied.items():
        normalized_key = (key[0].lower(), key[1]) if key[1] == "header" else key
        if normalized_key not in defined:
            _add_issue(
                issues,
                f"{path}.parameters",
                f"Parameter '{key[0]}' in '{key[1]}' is not defined by the target operation.",
                file_path,
            )
            continue
        _validate_parameter_value(
            parameter,
            defined[normalized_key],
            f"{path}.parameters",
            file_path,
            issues,
        )
    for key, parameter in defined.items():
        if parameter.get("required") is True and key not in {
            ((name.lower(), location) if location == "header" else (name, location))
            for name, location in supplied
        }:
            _add_issue(
                issues,
                f"{path}.parameters",
                f"Required parameter '{key[0]}' in '{key[1]}' is not supplied.",
                file_path,
            )


def _validate_parameter_value(
    supplied: Mapping[str, Any],
    defined: Mapping[str, Any],
    path: str,
    file_path: str,
    issues: list[ToolError],
) -> None:
    value = supplied.get("value")
    schema = defined.get("schema")
    if _contains_runtime_expression(value) or not isinstance(schema, Mapping):
        return
    try:
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(value)
    except SchemaError as error:
        _add_issue(
            issues,
            path,
            f"OpenAPI parameter schema is invalid: {error.message}.",
            file_path,
            code="ARAZZO_PARAMETER_SCHEMA_INVALID",
        )
    except ValidationError as error:
        _add_issue(
            issues,
            path,
            f"Parameter '{supplied.get('name')}' value does not satisfy its OpenAPI schema: {error}.",
            file_path,
            code="ARAZZO_PARAMETER_VALUE_INVALID",
        )


def _contains_runtime_expression(value: Any) -> bool:
    return isinstance(value, str) and ("{$" in value or value.startswith("$"))


def _effective_parameters(
    path_item: Mapping[str, Any], operation: Mapping[str, Any]
) -> dict[tuple[str, str], Mapping[str, Any]]:
    parameters: dict[tuple[str, str], Mapping[str, Any]] = {}
    for source in (path_item.get("parameters"), operation.get("parameters")):
        if not _is_sequence(source):
            continue
        for parameter in source:
            if not isinstance(parameter, Mapping) or "$ref" in parameter:
                continue
            name = parameter.get("name")
            location = parameter.get("in")
            if not isinstance(name, str) or not isinstance(location, str):
                continue
            key = (name.lower(), location) if location == "header" else (name, location)
            parameters[key] = parameter
    return parameters


def _is_sequence(value: Any) -> TypeGuard[Sequence[Any]]:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


def _add_issue(
    issues: list[ToolError],
    path: str,
    message: str,
    file_path: str,
    code: str = "ARAZZO_PARAMETER_UNRESOLVED",
) -> None:
    issues.append(
        ToolError(
            code,
            f"{message} Found at {path}.",
            ExitCode.VALIDATION_ERROR,
            file_path,
        )
    )
