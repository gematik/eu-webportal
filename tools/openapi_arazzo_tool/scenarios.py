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

"""Sequential, isolated workflow test scenarios."""

import ipaddress
import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .arazzo.loader import load_arazzo_document
from .arazzo.runner import WorkflowResult, list_workflows, run_workflow
from .cross_validation.sources import resolve_sources
from .errors import ExitCode, ToolError
from .http.execution import NetworkPolicy
from .mocking.model import generate_mock_routes
from .mocking.server import create_mock_server
from .openapi.bundle import bundle_document
from .openapi.loader import load_openapi_document


@dataclass(frozen=True)
class ScenarioResult:
    """Result of one independent test scenario."""

    name: str
    passed: bool
    workflow: WorkflowResult | None
    error: str | None = None
    mock_scenario: tuple[str, ...] = ()


def run_scenarios(
    config: Mapping[str, Any],
    policy: NetworkPolicy,
    *,
    workflow_timeout_seconds: float,
) -> tuple[ScenarioResult, ...]:
    """Run sorted scenario files sequentially with a fresh server for each."""
    tests = config.get("tests")
    if not isinstance(tests, Mapping) or not isinstance(tests.get("path"), str):
        raise _config_error(
            "tests.path must name a directory of scenario YAML/JSON files."
        )
    root = Path(tests["path"]).resolve()
    if not root.is_dir():
        raise _config_error(f"Scenario directory '{root}' does not exist.")
    files = sorted(
        path
        for path in root.iterdir()
        if path.suffix.lower() in {".yaml", ".yml", ".json"}
    )
    if not files:
        raise _config_error(f"Scenario directory '{root}' contains no scenario files.")
    mock = config.get("mock")
    if not isinstance(mock, Mapping) or mock.get("bindHost") not in {
        "127.0.0.1",
        "::1",
    }:
        raise _config_error("run-tests requires explicit loopback mock.bindHost.")
    bind_host = mock["bindHost"]
    port = mock.get("port", 0)
    seed = mock.get("seed", 0)
    if not isinstance(port, int) or isinstance(port, bool) or not 0 <= port <= 65535:
        raise _config_error("mock.port must be an integer between 0 and 65535.")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise _config_error("mock.seed must be an integer.")
    allowed_roots = config["security"]["allowedRefRoots"]
    documents = [
        bundle_document(load_openapi_document(path), allowed_roots)
        for path in config["openapi"]
    ]
    workflows = []
    for path in config["arazzo"]:
        document = load_arazzo_document(path)
        workflows.append((document, resolve_sources(document, allowed_roots)))

    results: list[ScenarioResult] = []
    for path in files:
        if path.is_symlink() or root not in path.resolve().parents:
            raise _config_error(f"Scenario '{path}' escapes configured directory.")
        scenario = _load_scenario(path)
        workflow_id = scenario["workflow"]
        matches = [
            (doc, sources)
            for doc, sources in workflows
            if workflow_id in list_workflows(doc)
        ]
        if len(matches) != 1:
            raise _config_error(
                f"Scenario '{path.name}' must resolve exactly one workflow."
            )
        selections = _mock_selections(scenario, config.get("scenarios", {}))
        routes = generate_mock_routes(documents, scenario=selections, seed=seed)
        server = create_mock_server(
            bind_host,
            port,
            routes,
            validate_requests=tests.get("validateRequests", True) is True,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            address = ipaddress.ip_address(bind_host)
            host = f"[{address}]" if address.version == 6 else str(address)
            base_url = f"http://{host}:{server.server_port}"
            test_policy = NetworkPolicy(
                frozenset({bind_host}),
                frozenset({server.server_port}),
                allow_private_addresses=True,
                request_timeout_seconds=policy.request_timeout_seconds,
                redirect_limit=policy.redirect_limit,
                max_response_bytes=policy.max_response_bytes,
            )
            try:
                result = run_workflow(
                    matches[0][0],
                    matches[0][1],
                    workflow_id,
                    scenario["inputs"],
                    test_policy,
                    configured_base_url=base_url,
                    workflow_timeout_seconds=workflow_timeout_seconds,
                    validate_requests=tests.get("validateRequests", True) is True,
                    validate_responses=tests.get("validateResponses", True) is True,
                    return_failed_result=True,
                    unauthenticated_mock_operations=frozenset(
                        operation_id
                        for operation_id, option in selections.items()
                        if option.get("response") == 401
                    ),
                )
                passed = _matches_expectation(result, scenario["expect"])
                results.append(
                    ScenarioResult(
                        path.name, passed, result, mock_scenario=tuple(selections)
                    )
                )
            except ToolError as error:
                results.append(
                    ScenarioResult(
                        path.name, False, None, str(error), tuple(selections)
                    )
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        if not results[-1].passed and tests.get("failFast") is True:
            break
    return tuple(results)


def _load_scenario(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as stream:
            value = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as error:
        raise _config_error(f"Cannot parse scenario '{path}': {error}.") from error
    if not isinstance(value, dict) or not isinstance(value.get("workflow"), str):
        raise _config_error(f"Scenario '{path}' requires a workflow identifier.")
    if set(value) - {"workflow", "inputs", "mockScenario", "expect", "environment"}:
        raise _config_error(f"Scenario '{path}' contains unsupported fields.")
    inputs = value.setdefault("inputs", {})
    expected = value.setdefault("expect", {"workflow": "success"})
    if not isinstance(inputs, dict) or not isinstance(expected, dict):
        raise _config_error(f"Scenario '{path}' inputs and expect must be mappings.")
    if expected.get("workflow") not in {"success", "failure"} or set(expected) - {
        "workflow",
        "step",
        "status",
    }:
        raise _config_error(f"Scenario '{path}' has invalid expect fields.")
    if "step" in expected and not isinstance(expected["step"], str):
        raise _config_error(f"Scenario '{path}' expect.step must be a string.")
    if "status" in expected and (
        not isinstance(expected["status"], int) or isinstance(expected["status"], bool)
    ):
        raise _config_error(f"Scenario '{path}' expect.status must be an integer.")
    environment = value.get("environment", {})
    if not isinstance(environment, dict) or environment:
        raise _config_error(
            "Scenario environment overrides are not supported in local mock runs."
        )
    return value


def _mock_selections(
    scenario: Mapping[str, Any],
    catalog: Any,
) -> dict[str, Mapping[str, Any]]:
    selected = scenario.get("mockScenario", {})
    if not isinstance(selected, Mapping) or not isinstance(catalog, Mapping):
        raise _config_error("mockScenario and scenarios must be mappings.")
    result = {}
    for operation_id, name in selected.items():
        if not isinstance(operation_id, str) or not isinstance(name, str):
            raise _config_error("mockScenario must map operationIds to scenario names.")
        definition = catalog.get(name)
        option = (
            definition.get(operation_id) if isinstance(definition, Mapping) else None
        )
        if not isinstance(option, Mapping):
            raise _config_error(
                f"Scenario '{name}' has no selection for operation '{operation_id}'."
            )
        result[operation_id] = option
    return result


def _matches_expectation(result: WorkflowResult, expected: Mapping[str, Any]) -> bool:
    if result.success != (expected["workflow"] == "success"):
        return False
    if "step" not in expected and "status" not in expected:
        return True
    return any(
        ("step" not in expected or step.step_id == expected["step"])
        and ("status" not in expected or step.status_code == expected["status"])
        for step in result.steps
    )


def scenario_json(results: tuple[ScenarioResult, ...]) -> str:
    """Serialize scenario results without exposing workflow inputs."""
    return json.dumps(
        [
            {
                "scenario": result.name,
                "passed": result.passed,
                "workflow": result.workflow.workflow_id if result.workflow else None,
                "steps": [
                    {
                        "stepId": step.step_id,
                        "statusCode": step.status_code,
                        "success": step.success,
                    }
                    for step in result.workflow.steps
                ]
                if result.workflow
                else [],
                "error": result.error,
            }
            for result in results
        ],
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _config_error(message: str) -> ToolError:
    return ToolError("SCENARIO_INVALID", message, ExitCode.CONFIGURATION_ERROR)
