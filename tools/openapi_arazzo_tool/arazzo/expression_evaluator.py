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

"""Safe runtime evaluation for parsed Arazzo expressions."""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from ..errors import ExitCode, ToolError
from .runtime_expressions import RuntimeExpression, parse_runtime_expressions

_MISSING = object()


@dataclass(frozen=True)
class HttpMessage:
    """HTTP values exposed to Arazzo runtime expressions."""

    headers: Mapping[str, Any] = field(default_factory=dict)
    query: Mapping[str, Any] = field(default_factory=dict)
    path: Mapping[str, Any] = field(default_factory=dict)
    body: Any = None


@dataclass(frozen=True)
class Message:
    """Async message values exposed by the expression grammar."""

    headers: Mapping[str, Any] = field(default_factory=dict)
    payload: Any = None


@dataclass(frozen=True)
class RuntimeContext:
    """Explicit data boundary available to runtime-expression evaluation."""

    url: str | None = None
    method: str | None = None
    status_code: int | None = None
    self_uri: str | None = None
    inputs: Mapping[str, Any] = field(default_factory=dict)
    outputs: Mapping[str, Any] = field(default_factory=dict)
    steps: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    workflows: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    request: HttpMessage = field(default_factory=HttpMessage)
    response: HttpMessage = field(default_factory=HttpMessage)
    message: Message = field(default_factory=Message)
    source_descriptions: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    components: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)


def evaluate_expression_string(value: str, context: RuntimeContext) -> Any:
    """Evaluate a full expression or interpolate embedded expressions."""
    try:
        expressions = parse_runtime_expressions(value)
    except ValueError as error:
        raise _evaluation_error(str(error)) from error
    if not expressions:
        return value
    if len(expressions) == 1 and _is_complete_expression(value, expressions[0]):
        return _evaluate_expression(expressions[0].value, context)

    result = value
    for expression in reversed(expressions):
        resolved = _stringify(_evaluate_expression(expression.value, context))
        start = expression.start - 1 if expression.embedded else expression.start
        result = f"{result[:start]}{resolved}{result[expression.end :]}"
    return result


def _evaluate_expression(expression: str, context: RuntimeContext) -> Any:
    base, pointer = _split_pointer(expression)
    value = _resolve_base(base, context)
    if value is _MISSING:
        raise _evaluation_error(
            f"Runtime expression '{expression}' cannot be resolved."
        )
    return (
        _resolve_json_pointer(value, pointer, expression)
        if pointer is not None
        else value
    )


def _resolve_base(expression: str, context: RuntimeContext) -> Any:
    optional_simple = {
        "$url": context.url,
        "$method": context.method,
        "$statusCode": context.status_code,
        "$self": context.self_uri,
    }
    if expression in optional_simple:
        value = optional_simple[expression]
        return value if value is not None else _MISSING
    payloads = {
        "$request.body": context.request.body,
        "$response.body": context.response.body,
        "$message.payload": context.message.payload,
    }
    if expression in payloads:
        return payloads[expression]

    resolvers = (
        ("$inputs.", context.inputs),
        ("$outputs.", context.outputs),
        ("$request.query.", context.request.query),
        ("$request.path.", context.request.path),
    )
    for prefix, values in resolvers:
        if expression.startswith(prefix):
            return values.get(expression[len(prefix) :], _MISSING)

    if expression.startswith("$request.header."):
        return _header(
            context.request.headers, expression.removeprefix("$request.header.")
        )
    if expression.startswith("$response.header."):
        return _header(
            context.response.headers, expression.removeprefix("$response.header.")
        )
    if expression.startswith("$message.header."):
        return _header(
            context.message.headers, expression.removeprefix("$message.header.")
        )
    if expression.startswith("$steps."):
        return _nested_reference(expression, "$steps.", context.steps, "outputs")
    if expression.startswith("$workflows."):
        return _workflow_reference(expression, context.workflows)
    if expression.startswith("$sourceDescriptions."):
        return _source_reference(expression, context.source_descriptions)
    if expression.startswith("$components."):
        return _component_reference(expression, context.components)
    return _MISSING


def _nested_reference(
    expression: str,
    prefix: str,
    values: Mapping[str, Mapping[str, Any]],
    required_field: str,
) -> Any:
    parts = expression.removeprefix(prefix).split(".", 2)
    if len(parts) != 3 or parts[1] != required_field:
        return _MISSING
    container = values.get(parts[0])
    nested = container.get(required_field) if isinstance(container, Mapping) else None
    return nested.get(parts[2], _MISSING) if isinstance(nested, Mapping) else _MISSING


def _workflow_reference(
    expression: str,
    workflows: Mapping[str, Mapping[str, Any]],
) -> Any:
    parts = expression.removeprefix("$workflows.").split(".", 2)
    if len(parts) != 3 or parts[1] not in {"inputs", "outputs"}:
        return _MISSING
    workflow = workflows.get(parts[0])
    values = workflow.get(parts[1]) if isinstance(workflow, Mapping) else None
    return values.get(parts[2], _MISSING) if isinstance(values, Mapping) else _MISSING


def _source_reference(
    expression: str,
    sources: Mapping[str, Mapping[str, Any]],
) -> Any:
    remainder = expression.removeprefix("$sourceDescriptions.")
    source_name, separator, reference = remainder.partition(".")
    source = sources.get(source_name)
    if not separator or not isinstance(source, Mapping):
        return _MISSING
    operations = source.get("operations")
    if isinstance(operations, Mapping) and reference in operations:
        return operations[reference]
    return source.get(reference, _MISSING)


def _component_reference(
    expression: str,
    components: Mapping[str, Mapping[str, Any]],
) -> Any:
    parts = expression.removeprefix("$components.").split(".", 1)
    if len(parts) != 2:
        return _MISSING
    values = components.get(parts[0])
    return values.get(parts[1], _MISSING) if isinstance(values, Mapping) else _MISSING


def _header(headers: Mapping[str, Any], name: str) -> Any:
    normalized = name.lower()
    for header, value in headers.items():
        if isinstance(header, str) and header.lower() == normalized:
            return value
    return _MISSING


def _split_pointer(expression: str) -> tuple[str, str | None]:
    base, marker, pointer = expression.partition("#")
    return base, pointer if marker else None


def _resolve_json_pointer(value: Any, pointer: str, expression: str) -> Any:
    if pointer == "":
        return value
    current = value
    for raw_token in pointer[1:].split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping):
            current = current.get(token, _MISSING)
        elif isinstance(current, list) and token.isdigit():
            index = int(token)
            current = current[index] if index < len(current) else _MISSING
        else:
            current = _MISSING
        if current is _MISSING:
            raise _evaluation_error(
                f"JSON Pointer '#{pointer}' in runtime expression '{expression}' cannot be resolved."
            )
    return current


def _is_complete_expression(value: str, expression: RuntimeExpression) -> bool:
    return (
        not expression.embedded
        and expression.start == 0
        and expression.end == len(value)
    )


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return str(value)


def _evaluation_error(message: str) -> ToolError:
    return ToolError(
        "ARAZZO_EXPRESSION_EVALUATION_FAILED",
        message,
        ExitCode.TEST_ERROR,
    )
