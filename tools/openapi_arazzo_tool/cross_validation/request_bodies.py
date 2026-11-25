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

"""Cross-validation of Arazzo request bodies against OpenAPI operations."""

from collections.abc import Mapping, Sequence
from typing import Any, TypeGuard

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from ..arazzo.model import ArazzoDocument
from ..errors import ExitCode, ToolError
from .parameters import _resolve_operation
from .sources import ResolvedSources


def find_request_body_issues(
    document: ArazzoDocument, sources: ResolvedSources
) -> list[ToolError]:
    """Check request-body presence, media type, and static payload schemas."""
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
            operation = _resolve_operation(step, sources)
            if operation is None:
                continue
            _validate_step_body(
                step,
                operation[1],
                f"$.workflows[{workflow_index}].steps[{step_index}]",
                document.path,
                issues,
            )
    return issues


def _validate_step_body(
    step: Mapping[str, Any],
    operation: Mapping[str, Any],
    path: str,
    file_path: str,
    issues: list[ToolError],
) -> None:
    supplied = step.get("requestBody")
    definition = operation.get("requestBody")
    if supplied is None:
        if isinstance(definition, Mapping) and definition.get("required") is True:
            _add_issue(
                issues, path, "Required request body is not supplied.", file_path
            )
        return
    if not isinstance(definition, Mapping) or "$ref" in definition:
        _add_issue(
            issues,
            path,
            "Request body is not supported by the target operation.",
            file_path,
        )
        return
    if not isinstance(supplied, Mapping):
        return
    content_type = supplied.get("contentType")
    content = definition.get("content")
    if not isinstance(content_type, str) or not isinstance(content, Mapping):
        return
    media = content.get(content_type) or content.get("*/*")
    if not isinstance(media, Mapping):
        _add_issue(
            issues,
            f"{path}.requestBody.contentType",
            f"Content type '{content_type}' is not supported.",
            file_path,
        )
        return
    payload = supplied.get("payload")
    schema = media.get("schema")
    if _contains_runtime_expression(payload) or not isinstance(schema, Mapping):
        return
    try:
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(payload)
    except SchemaError:
        _add_issue(
            issues,
            f"{path}.requestBody.payload",
            "OpenAPI request-body schema is invalid.",
            file_path,
        )
    except ValidationError as error:
        _add_issue(
            issues,
            f"{path}.requestBody.payload",
            f"Payload does not satisfy the OpenAPI schema: {error.message}.",
            file_path,
        )


def _contains_runtime_expression(value: Any) -> bool:
    return isinstance(value, str) and ("{$" in value or value.startswith("$"))


def _is_sequence(value: Any) -> TypeGuard[Sequence[Any]]:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


def _add_issue(
    issues: list[ToolError], path: str, message: str, file_path: str
) -> None:
    issues.append(
        ToolError(
            "ARAZZO_REQUEST_BODY_INVALID",
            f"{message} Found at {path}.",
            ExitCode.VALIDATION_ERROR,
            file_path,
        )
    )
