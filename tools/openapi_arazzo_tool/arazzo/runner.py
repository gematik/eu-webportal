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

"""Direct execution of the supported Arazzo 1.1 workflow subset."""

import hashlib
import json
import re
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, TypeGuard
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from ..cross_validation.parameters import _resolve_operation_with_source
from ..cross_validation.sources import ResolvedSources
from ..errors import ExitCode, ToolError
from ..http.auth import authorize_request, redact
from ..http.execution import HttpResponse, NetworkPolicy, execute_http_request
from ..http.requests import HttpRequest, build_http_request
from ..http.targets import resolve_target_url
from ..openapi.contracts import (
    effective_runtime_parameters,
    validate_request_contract,
    validate_response_contract,
)
from .criteria import evaluate_criteria
from .expression_evaluator import (
    HttpMessage,
    RuntimeContext,
    evaluate_expression_string,
)
from .model import ArazzoDocument

HttpExecutor = Callable[[HttpRequest, NetworkPolicy], HttpResponse]


@dataclass(frozen=True)
class StepResult:
    """Observable result of one completed workflow step."""

    step_id: str
    success: bool
    status_code: int
    outputs: Mapping[str, Any] = field(default_factory=dict)
    operation: str | None = None
    method: str | None = None
    url: str | None = None
    duration_ms: float = 0.0
    assertion: str | None = None
    expected: str | None = None
    actual: str | None = None
    openapi_source: str | None = None
    arazzo_source: str | None = None


@dataclass(frozen=True)
class WorkflowResult:
    """Final workflow execution result."""

    workflow_id: str
    success: bool
    outputs: Mapping[str, Any]
    steps: tuple[StepResult, ...]


def list_workflows(document: ArazzoDocument) -> tuple[str, ...]:
    """Return workflow identifiers in document order."""
    workflows = document.raw.get("workflows")
    if not _is_sequence(workflows):
        return ()
    return tuple(
        workflow["workflowId"]
        for workflow in workflows
        if isinstance(workflow, Mapping) and isinstance(workflow.get("workflowId"), str)
    )


def run_workflow(
    document: ArazzoDocument,
    sources: ResolvedSources,
    workflow_id: str,
    inputs: Mapping[str, Any],
    policy: NetworkPolicy,
    *,
    configured_base_url: str | None = None,
    server_variables: Mapping[str, str] | None = None,
    workflow_timeout_seconds: float = 60.0,
    validate_requests: bool = True,
    validate_responses: bool = True,
    return_failed_result: bool = False,
    auth: Mapping[str, Any] | None = None,
    trusted: bool = False,
    unauthenticated_mock_operations: frozenset[str] = frozenset(),
    executor: HttpExecutor = execute_http_request,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> WorkflowResult:
    """Execute one workflow directly against its resolved OpenAPI operations."""
    workflows = _workflow_map(document)
    workflow = workflows.get(workflow_id)
    if workflow is None:
        raise _runner_error(f"Workflow '{workflow_id}' does not exist.")
    if workflow_timeout_seconds <= 0:
        raise _runner_error("Workflow timeout must be positive.")
    _validate_inputs(workflow, inputs)
    workflow_sha256 = None
    if trusted and auth:
        try:
            workflow_sha256 = hashlib.sha256(
                Path(document.path).read_bytes()
            ).hexdigest()
        except OSError as error:
            raise _runner_error("Trusted workflow document cannot be read.") from error

    deadline = clock() + workflow_timeout_seconds
    step_results: list[StepResult] = []
    step_contexts: dict[str, Mapping[str, Any]] = {}
    workflow_contexts: dict[str, Mapping[str, Any]] = {
        workflow_id: {"inputs": dict(inputs), "outputs": {}}
    }
    current_workflow_id = workflow_id
    current_step_index = 0
    retries: dict[tuple[str, str, str], int] = {}

    while True:
        _check_deadline(deadline, clock)
        current_workflow = workflows[current_workflow_id]
        steps = current_workflow["steps"]
        if current_step_index >= len(steps):
            outputs = _evaluate_outputs(
                current_workflow.get("outputs"),
                RuntimeContext(
                    inputs=inputs,
                    steps=step_contexts,
                    workflows=workflow_contexts,
                ),
            )
            workflow_contexts[current_workflow_id] = {
                "inputs": dict(inputs),
                "outputs": outputs,
            }
            return WorkflowResult(
                current_workflow_id,
                True,
                outputs,
                tuple(step_results),
            )

        step = steps[current_step_index]
        step_id = step["stepId"]
        result, context = _execute_step(
            step,
            current_workflow_id,
            inputs,
            step_contexts,
            workflow_contexts,
            sources,
            replace(
                policy,
                request_timeout_seconds=min(
                    policy.request_timeout_seconds,
                    _remaining_seconds(deadline, clock),
                ),
            ),
            configured_base_url,
            server_variables,
            executor,
            validate_requests,
            validate_responses,
            auth,
            trusted,
            workflow_sha256,
            document.path,
            unauthenticated_mock_operations,
        )
        _check_deadline(deadline, clock)
        step_results.append(result)
        step_contexts[step_id] = {"outputs": dict(result.outputs)}
        action = _select_action(
            step.get("onSuccess") if result.success else step.get("onFailure"),
            context,
            retries,
            current_workflow_id,
            step_id,
            sleep,
            deadline,
            clock,
        )
        if action is None:
            if not result.success:
                if return_failed_result:
                    return WorkflowResult(
                        current_workflow_id, False, {}, tuple(step_results)
                    )
                raise _runner_error(
                    f"Step '{step_id}' failed without an applicable onFailure action."
                )
            current_step_index += 1
            continue
        action_type = action["type"]
        if action_type == "end":
            outputs = _evaluate_outputs(
                current_workflow.get("outputs"),
                RuntimeContext(
                    inputs=inputs, steps=step_contexts, workflows=workflow_contexts
                ),
            )
            return WorkflowResult(
                current_workflow_id,
                result.success,
                outputs,
                tuple(step_results),
            )
        if action_type == "retry":
            continue
        if "workflowId" in action:
            current_workflow_id = action["workflowId"]
            workflow_contexts.setdefault(
                current_workflow_id,
                {"inputs": dict(inputs), "outputs": {}},
            )
            current_step_index = 0
            continue
        current_step_index = _step_index(current_workflow, action["stepId"])


def _execute_step(
    step: Mapping[str, Any],
    workflow_id: str,
    inputs: Mapping[str, Any],
    steps: Mapping[str, Mapping[str, Any]],
    workflows: Mapping[str, Mapping[str, Any]],
    sources: ResolvedSources,
    policy: NetworkPolicy,
    configured_base_url: str | None,
    server_variables: Mapping[str, str] | None,
    executor: HttpExecutor,
    validate_requests: bool,
    validate_responses: bool,
    auth: Mapping[str, Any] | None,
    trusted: bool,
    workflow_sha256: str | None,
    arazzo_path: str,
    unauthenticated_mock_operations: frozenset[str],
) -> tuple[StepResult, RuntimeContext]:
    resolved = _resolve_operation_with_source(step, sources)
    if resolved is None:
        raise _runner_error(
            f"Operation for step '{step['stepId']}' cannot be resolved."
        )
    source, path_item, operation = resolved
    source_path = next(
        (item.path for item in sources.sources.values() if item.raw is source),
        None,
    )
    operation_path, method = _operation_location(source, operation)
    base_url = resolve_target_url(
        source,
        path_item,
        operation,
        configured_base_url=configured_base_url,
        server_variables=server_variables,
    )
    initial_context = RuntimeContext(
        inputs=inputs,
        steps=steps,
        workflows=workflows,
        source_descriptions=_source_context(sources),
    )
    parameter_values, request_message = _parameter_values(step, initial_context)
    body_payload, body_content_type = _request_body(step, initial_context)
    request = build_http_request(
        method,
        base_url,
        operation_path,
        tuple(effective_runtime_parameters(source, path_item, operation).values()),
        parameter_values,
        body_payload=body_payload,
        body_content_type=body_content_type,
    )
    if validate_requests:
        validate_request_contract(
            source,
            path_item,
            operation,
            parameter_values,
            request,
            body_payload,
            body_content_type,
        )
    mock_unauthenticated = operation.get(
        "operationId"
    ) in unauthenticated_mock_operations and urlsplit(request.url).hostname in {
        "127.0.0.1",
        "::1",
    }
    secrets: tuple[str, ...]
    if mock_unauthenticated:
        authorized, secrets = request, ()
    else:
        authorized, secrets = authorize_request(
            request,
            source,
            operation,
            workflow_id,
            operation_path,
            auth,
            trusted=trusted,
            workflow_sha256=workflow_sha256,
        )
    started = time.perf_counter()
    try:
        response = executor(
            authorized,
            replace(policy, redirect_limit=0) if secrets else policy,
        )
        response_body = (
            validate_response_contract(source, operation, response)
            if validate_responses
            else _response_body(response)
        )
    except ToolError as error:
        raise ToolError(
            error.code, redact(error.message, secrets), error.exit_code, error.file
        ) from error
    context = RuntimeContext(
        url=request.url,
        method=request.method,
        status_code=response.status_code,
        inputs=inputs,
        steps=steps,
        workflows=workflows,
        request=HttpMessage(
            headers=request.headers,
            query=request_message.query,
            path=request_message.path,
            body=body_payload,
        ),
        response=HttpMessage(headers=response.headers, body=response_body),
        source_descriptions=_source_context(sources),
    )
    criteria = step.get("successCriteria")
    if _is_sequence(criteria):
        success = evaluate_criteria(criteria, context)
        assertion = " && ".join(item["condition"] for item in criteria)
    else:
        success = 200 <= response.status_code < 300
        assertion = "HTTP 2xx"
    outputs = redact(_evaluate_outputs(step.get("outputs"), context), secrets)
    match = re.fullmatch(r"\$statusCode\s*==\s*(\d{3})", assertion)
    expected = match.group(1) if match else "true"
    actual = str(response.status_code) if match else str(success).lower()
    return StepResult(
        step["stepId"],
        success,
        response.status_code,
        outputs,
        operation=step.get("operationId", step.get("operationPath")),
        method=request.method,
        url=redact(request.url, secrets),
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
        assertion=assertion,
        expected=expected,
        actual=actual,
        openapi_source=f"{source_path}#{operation_path}"
        if source_path
        else operation_path,
        arazzo_source=f"{arazzo_path}#{step['stepId']}",
    ), context


def _parameter_values(
    step: Mapping[str, Any],
    context: RuntimeContext,
) -> tuple[dict[tuple[str, str], Any], HttpMessage]:
    values: dict[tuple[str, str], Any] = {}
    query: dict[str, Any] = {}
    path: dict[str, Any] = {}
    parameters = step.get("parameters")
    if not _is_sequence(parameters):
        return values, HttpMessage()
    for parameter in parameters:
        value = _evaluate_value(parameter["value"], context)
        name = parameter["name"]
        location = parameter["in"]
        values[(name, location)] = value
        if location == "query":
            query[name] = value
        elif location == "path":
            path[name] = value
    return values, HttpMessage(query=query, path=path)


def _request_body(
    step: Mapping[str, Any],
    context: RuntimeContext,
) -> tuple[Any, str | None]:
    request_body = step.get("requestBody")
    if not isinstance(request_body, Mapping):
        return None, None
    return _evaluate_value(request_body.get("payload"), context), request_body[
        "contentType"
    ]


def _evaluate_value(value: Any, context: RuntimeContext) -> Any:
    if isinstance(value, str):
        return evaluate_expression_string(value, context)
    if isinstance(value, Mapping):
        return {key: _evaluate_value(item, context) for key, item in value.items()}
    if _is_sequence(value):
        return [_evaluate_value(item, context) for item in value]
    return value


def _evaluate_outputs(value: Any, context: RuntimeContext) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        name: evaluate_expression_string(expression, context)
        for name, expression in value.items()
    }


def _response_body(response: HttpResponse) -> Any:
    content_type = (
        response.headers.get("content-type", "").partition(";")[0].strip().lower()
    )
    if not response.body:
        return None
    if content_type == "application/json" or content_type.endswith("+json"):
        try:
            return json.loads(response.body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise _runner_error(
                "HTTP response declares invalid JSON content."
            ) from error
    if content_type.startswith("text/") or content_type in {
        "application/xml",
        "application/xhtml+xml",
    }:
        try:
            return response.body.decode("utf-8")
        except UnicodeDecodeError as error:
            raise _runner_error("HTTP text response is not valid UTF-8.") from error
    return response.body


def _select_action(
    value: Any,
    context: RuntimeContext,
    retries: dict[tuple[str, str, str], int],
    workflow_id: str,
    step_id: str,
    sleep: Callable[[float], None],
    deadline: float,
    clock: Callable[[], float],
) -> Mapping[str, Any] | None:
    if not _is_sequence(value):
        return None
    for action in value:
        if not isinstance(action, Mapping):
            raise _runner_error("Workflow action must be a mapping.")
        criteria = action.get("criteria")
        if _is_sequence(criteria) and not evaluate_criteria(criteria, context):
            continue
        if action["type"] != "retry":
            return action
        key = (workflow_id, step_id, action["name"])
        count = retries.get(key, 0)
        limit = action.get("retryLimit", 1)
        if count >= limit:
            continue
        retries[key] = count + 1
        delay = float(action.get("retryAfter", 0))
        if delay:
            if clock() + delay > deadline:
                raise _runner_error("Workflow timed out before retry delay completed.")
            sleep(delay)
        return action
    return None


def _validate_inputs(workflow: Mapping[str, Any], inputs: Mapping[str, Any]) -> None:
    schema = workflow.get("inputs")
    if not isinstance(schema, Mapping):
        if inputs:
            raise _runner_error("Workflow does not declare inputs.")
        return
    try:
        Draft202012Validator(schema).validate(dict(inputs))
    except ValidationError as error:
        raise _runner_error(f"Workflow inputs are invalid: {error.message}.") from error


def _operation_location(
    document: Mapping[str, Any],
    operation: Mapping[str, Any],
) -> tuple[str, str]:
    paths = document.get("paths")
    if isinstance(paths, Mapping):
        for path, path_item in paths.items():
            if not isinstance(path_item, Mapping):
                continue
            for method, candidate in path_item.items():
                if candidate is operation:
                    return path, method.upper()
    raise _runner_error(
        "Resolved operation is not an executable OpenAPI path operation."
    )


def _source_context(sources: ResolvedSources) -> dict[str, Mapping[str, Any]]:
    return {name: {"url": source.path} for name, source in sources.sources.items()}


def _workflow_map(document: ArazzoDocument) -> dict[str, Mapping[str, Any]]:
    workflows = document.raw.get("workflows")
    if not _is_sequence(workflows):
        return {}
    return {
        workflow["workflowId"]: workflow
        for workflow in workflows
        if isinstance(workflow, Mapping)
        and isinstance(workflow.get("workflowId"), str)
        and _is_sequence(workflow.get("steps"))
    }


def _step_index(workflow: Mapping[str, Any], step_id: str) -> int:
    for index, step in enumerate(workflow["steps"]):
        if step["stepId"] == step_id:
            return index
    raise _runner_error(f"Goto step '{step_id}' does not exist.")


def _check_deadline(deadline: float, clock: Callable[[], float]) -> None:
    if clock() >= deadline:
        raise _runner_error("Workflow execution timed out.")


def _remaining_seconds(deadline: float, clock: Callable[[], float]) -> float:
    remaining = deadline - clock()
    if remaining <= 0:
        raise _runner_error("Workflow execution timed out.")
    return remaining


def _is_sequence(value: Any) -> TypeGuard[Sequence[Any]]:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


def _runner_error(message: str) -> ToolError:
    return ToolError("WORKFLOW_EXECUTION_FAILED", message, ExitCode.TEST_ERROR)
