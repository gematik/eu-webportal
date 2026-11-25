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

import argparse
import contextlib
import io
import json
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .arazzo.actions import find_action_issues
from .arazzo.control_flow import find_control_flow_issues
from .arazzo.criterion_features import find_criterion_feature_issues
from .arazzo.dependencies import find_dependency_issues
from .arazzo.fields import find_field_issues
from .arazzo.inputs import find_input_issues
from .arazzo.loader import load_arazzo_document
from .arazzo.outputs import find_output_issues
from .arazzo.references import find_step_output_reference_issues
from .arazzo.runner import list_workflows, run_workflow
from .arazzo.runtime_expressions import find_runtime_expression_issues
from .arazzo.structure import find_structure_issues as find_arazzo_structure_issues
from .arazzo.workflows import find_workflow_issues
from .config import load_config
from .cross_validation.expressions import find_expression_dependency_issues
from .cross_validation.operation_paths import find_operation_path_issues
from .cross_validation.operations import (
    find_operation_id_issues as find_cross_operation_id_issues,
)
from .cross_validation.parameters import (
    find_parameter_issues as find_cross_parameter_issues,
)
from .cross_validation.request_bodies import (
    find_request_body_issues as find_cross_request_body_issues,
)
from .cross_validation.responses import find_response_reference_issues
from .cross_validation.sources import resolve_sources
from .errors import ExitCode, ToolError
from .http.execution import NetworkPolicy
from .mocking.lifecycle import serve_mock_server
from .mocking.model import MockRoute, generate_mock_routes
from .mocking.package import generator_version, load_mock_package, write_mock_package
from .mocking.server import create_mock_server
from .mocking.sources import collect_package_sources
from .openapi.bundle import bundle_document
from .openapi.examples import find_example_issues
from .openapi.loader import load_openapi_document
from .openapi.model import OpenApiDocument
from .openapi.operations import find_operation_id_issues
from .openapi.parameters import find_parameter_issues
from .openapi.refs import find_ref_issues
from .openapi.request_bodies import find_request_body_issues
from .openapi.responses import find_response_issues
from .openapi.schemas import find_schema_issues
from .openapi.security import find_security_issues
from .openapi.structure import find_structure_issues as find_openapi_structure_issues
from .reporting import render_console, write_reports
from .scenarios import run_scenarios, scenario_json

COMMANDS = (
    "validate-openapi",
    "validate-arazzo",
    "validate-all",
    "generate-mocks",
    "start-mocks",
    "stop-mocks",
    "list-workflows",
    "run-workflow",
    "run-tests",
    "report",
    "explain",
)


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        prog="tool",
        description="OpenAPI and Arazzo mocking and workflow test tool",
    )
    cli.add_argument("command", choices=COMMANDS, nargs="?")
    cli.add_argument("workflow", nargs="?")
    cli.add_argument(
        "--input",
        action="append",
        default=[],
        metavar="NAME=JSON",
        help="Workflow input as a JSON value; repeat for multiple inputs.",
    )
    cli.add_argument("--config", default="tool.yaml")
    cli.add_argument("--output", help="Output directory for a generated mock package.")
    cli.add_argument("--package-dir", help="Run a previously generated mock package.")
    cli.add_argument("--bind-host", help="Override the package runtime bind address.")
    cli.add_argument("--port", type=int, help="Override the package runtime port.")
    cli.add_argument(
        "--log-level", choices=("error", "warn", "info", "debug"), default="info"
    )
    return cli


def _validate_openapi(config: dict) -> int:
    paths = config.get("openapi") or []
    if not paths:
        raise ToolError(
            "CONFIG_INVALID",
            "No OpenAPI documents configured. Set 'openapi' in the configuration.",
            ExitCode.CONFIGURATION_ERROR,
        )

    allowed_ref_roots = (config.get("security") or {}).get("allowedRefRoots") or []
    if not allowed_ref_roots:
        raise ToolError(
            "CONFIG_INVALID",
            "No allowed $ref root directories configured. Set "
            "'security.allowedRefRoots' explicitly; there is no permissive "
            "default for local file access.",
            ExitCode.CONFIGURATION_ERROR,
        )

    failures: list[ToolError] = []
    for path in paths:
        try:
            document = load_openapi_document(path)
        except ToolError as error:
            print(error, file=sys.stderr)
            failures.append(error)
            continue

        issues = [
            *find_ref_issues(document, allowed_ref_roots),
            *find_openapi_structure_issues(document),
            *find_operation_id_issues(document),
            *find_parameter_issues(document),
            *find_example_issues(document),
            *find_request_body_issues(document),
            *find_response_issues(document),
            *find_schema_issues(document),
            *find_security_issues(document),
        ]
        if issues:
            for issue in issues:
                print(issue, file=sys.stderr)
            failures.extend(issues)
        else:
            print(f"OK {document.path} (OpenAPI {document.version})")

    if failures:
        raise ToolError(
            "OPENAPI_VALIDATION_FAILED",
            f"{len(failures)} issue(s) found across {len(paths)} OpenAPI document(s).",
            ExitCode.VALIDATION_ERROR,
        )
    return ExitCode.SUCCESS


def _validate_arazzo(config: dict) -> int:
    paths = config.get("arazzo") or []
    if not paths:
        raise ToolError(
            "CONFIG_INVALID",
            "No Arazzo documents configured. Set 'arazzo' in the configuration.",
            ExitCode.CONFIGURATION_ERROR,
        )

    failures: list[ToolError] = []
    for path in paths:
        try:
            document = load_arazzo_document(path)
        except ToolError as error:
            print(error, file=sys.stderr)
            failures.append(error)
            continue

        issues = [
            *find_field_issues(document),
            *find_arazzo_structure_issues(document),
            *find_workflow_issues(document),
            *find_input_issues(document),
            *find_output_issues(document),
            *find_criterion_feature_issues(document),
            *find_runtime_expression_issues(document),
            *find_step_output_reference_issues(document),
            *find_action_issues(document),
            *find_dependency_issues(document),
            *find_control_flow_issues(document),
        ]
        if issues:
            for issue in issues:
                print(issue, file=sys.stderr)
            failures.extend(issues)
        else:
            print(f"OK {document.path} (Arazzo {document.version})")

    if failures:
        raise ToolError(
            "ARAZZO_VALIDATION_FAILED",
            f"{len(failures)} issue(s) found across {len(paths)} Arazzo document(s).",
            ExitCode.VALIDATION_ERROR,
        )
    return ExitCode.SUCCESS


def _validate_all(config: dict) -> int:
    """Validate configured documents and resolve Arazzo OpenAPI sources."""
    _validate_openapi(config)
    _validate_arazzo(config)

    allowed_ref_roots = (config.get("security") or {}).get("allowedRefRoots") or []
    if not allowed_ref_roots:
        raise ToolError(
            "CONFIG_INVALID",
            "No allowed source root directories configured. Set "
            "'security.allowedRefRoots' explicitly.",
            ExitCode.CONFIGURATION_ERROR,
        )

    paths = config.get("arazzo") or []
    failures: list[ToolError] = []
    for path in paths:
        try:
            document = load_arazzo_document(path)
        except ToolError as error:
            failures.append(error)
            continue
        resolved_sources = resolve_sources(document, allowed_ref_roots)
        issues = [
            *resolved_sources.issues,
            *find_cross_operation_id_issues(document, resolved_sources),
            *find_operation_path_issues(document, resolved_sources),
            *find_expression_dependency_issues(document),
            *find_cross_parameter_issues(document, resolved_sources),
            *find_cross_request_body_issues(document, resolved_sources),
            *find_response_reference_issues(document, resolved_sources),
        ]
        for issue in issues:
            print(issue, file=sys.stderr)
        failures.extend(issues)
    if failures:
        raise ToolError(
            "CROSS_VALIDATION_FAILED",
            f"{len(failures)} cross-validation issue(s) found.",
            ExitCode.VALIDATION_ERROR,
        )
    return ExitCode.SUCCESS


def _list_workflows(config: dict) -> int:
    paths = config.get("arazzo") or []
    if not paths:
        raise ToolError(
            "CONFIG_INVALID",
            "No Arazzo documents configured. Set 'arazzo' in the configuration.",
            ExitCode.CONFIGURATION_ERROR,
        )
    for path in paths:
        document = load_arazzo_document(path)
        for workflow_id in list_workflows(document):
            print(f"{workflow_id}\t{document.path}")
    return ExitCode.SUCCESS


def _run_workflow(config: dict, workflow_id: str | None, raw_inputs: list[str]) -> int:
    if not workflow_id:
        raise ToolError(
            "CONFIG_INVALID",
            "run-workflow requires a workflow identifier.",
            ExitCode.CONFIGURATION_ERROR,
        )
    _validate_all(config)
    allowed_ref_roots = (config.get("security") or {}).get("allowedRefRoots") or []
    matches = []
    for path in config.get("arazzo") or []:
        document = load_arazzo_document(path)
        if workflow_id in list_workflows(document):
            matches.append((document, resolve_sources(document, allowed_ref_roots)))
    if not matches:
        raise ToolError(
            "WORKFLOW_EXECUTION_FAILED",
            f"Workflow '{workflow_id}' does not exist.",
            ExitCode.TEST_ERROR,
        )
    if len(matches) > 1:
        raise ToolError(
            "WORKFLOW_EXECUTION_FAILED",
            f"Workflow '{workflow_id}' is ambiguous across configured Arazzo documents.",
            ExitCode.TEST_ERROR,
        )
    network = config.get("network") or {}
    allowed_hosts = network.get("allowedHosts") or []
    allowed_ports = network.get("allowedPorts") or []
    if not _is_config_list(allowed_hosts) or not _is_config_list(allowed_ports):
        raise ToolError(
            "CONFIG_INVALID",
            "run-workflow requires explicit network.allowedHosts and network.allowedPorts.",
            ExitCode.CONFIGURATION_ERROR,
        )
    timeouts = config.get("timeouts") or {}
    policy = NetworkPolicy(
        frozenset(str(host) for host in allowed_hosts),
        frozenset(int(port) for port in allowed_ports),
        allow_private_addresses=network.get("allowPrivateAddresses") is True,
        request_timeout_seconds=_duration_seconds(
            timeouts.get("request", "5s"), "timeouts.request"
        ),
        redirect_limit=_non_negative_int(
            network.get("redirectLimit", 3), "network.redirectLimit"
        ),
        max_response_bytes=_positive_int(
            network.get("maxResponseBytes", 10 * 1024 * 1024),
            "network.maxResponseBytes",
        ),
    )
    result = run_workflow(
        matches[0][0],
        matches[0][1],
        workflow_id,
        _parse_inputs(raw_inputs),
        policy,
        configured_base_url=(config.get("target") or {}).get("baseUrl"),
        server_variables=(config.get("target") or {}).get("serverVariables"),
        workflow_timeout_seconds=_duration_seconds(
            timeouts.get("workflow", "60s"),
            "timeouts.workflow",
        ),
        validate_requests=(config.get("tests") or {}).get("validateRequests", True)
        is True,
        validate_responses=(config.get("tests") or {}).get("validateResponses", True)
        is True,
        auth=config.get("auth"),
        trusted=True,
    )
    print(
        json.dumps(
            {
                "workflowId": result.workflow_id,
                "success": result.success,
                "outputs": result.outputs,
                "steps": [
                    {
                        "stepId": step.step_id,
                        "success": step.success,
                        "statusCode": step.status_code,
                        "outputs": step.outputs,
                    }
                    for step in result.steps
                ],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return ExitCode.SUCCESS if result.success else ExitCode.TEST_ERROR


def _parse_inputs(values: list[str]) -> dict:
    inputs = {}
    for value in values:
        name, separator, raw = value.partition("=")
        if not separator or not name:
            raise ToolError(
                "CONFIG_INVALID",
                f"Workflow input '{value}' must use NAME=JSON syntax.",
                ExitCode.CONFIGURATION_ERROR,
            )
        try:
            inputs[name] = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ToolError(
                "CONFIG_INVALID",
                f"Workflow input '{name}' is not valid JSON: {error.msg}.",
                ExitCode.CONFIGURATION_ERROR,
            ) from error
    return inputs


def _duration_seconds(value: object, field: str) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        return float(value)
    if isinstance(value, str):
        match = re.fullmatch(r"(\d+(?:\.\d+)?)(ms|s|m)", value)
        if match:
            amount = float(match.group(1))
            return amount * {"ms": 0.001, "s": 1.0, "m": 60.0}[match.group(2)]
    raise ToolError(
        "CONFIG_INVALID",
        f"{field} must be a positive duration such as 500ms, 5s, or 1m.",
        ExitCode.CONFIGURATION_ERROR,
    )


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    raise ToolError(
        "CONFIG_INVALID",
        f"{field} must be a positive integer.",
        ExitCode.CONFIGURATION_ERROR,
    )


def _non_negative_int(value: object, field: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    raise ToolError(
        "CONFIG_INVALID",
        f"{field} must be a non-negative integer.",
        ExitCode.CONFIGURATION_ERROR,
    )


def _is_config_list(value: object) -> bool:
    return (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes))
        and bool(value)
    )


def _mock_documents(
    config: dict[str, Any], *, validate: bool = True
) -> list[OpenApiDocument]:
    if validate:
        with contextlib.redirect_stdout(io.StringIO()):
            _validate_openapi(config)
    allowed_ref_roots = (config.get("security") or {}).get("allowedRefRoots") or []
    return [
        bundle_document(load_openapi_document(path), allowed_ref_roots)
        for path in config.get("openapi") or []
    ]


def _mock_routes(config: dict[str, Any]) -> tuple[MockRoute, ...]:
    documents = _mock_documents(config)
    return _mock_routes_from_documents(config, documents)


def _mock_routes_from_documents(
    config: dict[str, Any], documents: list[OpenApiDocument]
) -> tuple[MockRoute, ...]:
    mock = config.get("mock") or {}
    scenario_name = mock.get("scenario")
    scenario = None
    if scenario_name is not None:
        scenarios = config.get("scenarios")
        if not isinstance(scenario_name, str) or not isinstance(scenarios, dict):
            raise ToolError(
                "CONFIG_INVALID",
                "mock.scenario requires a named top-level scenarios mapping.",
                ExitCode.CONFIGURATION_ERROR,
            )
        scenario = scenarios.get(scenario_name)
        if not isinstance(scenario, dict):
            raise ToolError(
                "CONFIG_INVALID",
                f"Mock scenario '{scenario_name}' does not exist.",
                ExitCode.CONFIGURATION_ERROR,
            )
    examples = mock.get("examples") or {}
    if not isinstance(examples, dict):
        raise ToolError(
            "CONFIG_INVALID",
            "mock.examples must map operationIds to example names.",
            ExitCode.CONFIGURATION_ERROR,
        )
    seed = mock.get("seed", 0)
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ToolError(
            "CONFIG_INVALID",
            "mock.seed must be an integer.",
            ExitCode.CONFIGURATION_ERROR,
        )
    return generate_mock_routes(
        documents,
        scenario=scenario,
        example_names=examples,
        seed=seed,
    )


def _generate_mocks(config: dict, output_directory: str | None = None) -> int:
    mock = config.get("mock") or {}
    package_version = mock.get("packageVersion")
    if not isinstance(package_version, str):
        raise ToolError(
            "CONFIG_INVALID",
            "generate-mocks requires mock.packageVersion using semantic versioning.",
            ExitCode.CONFIGURATION_ERROR,
        )
    with contextlib.redirect_stdout(io.StringIO()):
        if config.get("arazzo"):
            _validate_all(config)
        else:
            _validate_openapi(config)
    documents = _mock_documents(config, validate=False)
    routes = _mock_routes_from_documents(config, documents)
    sources = collect_package_sources(
        config.get("openapi") or [],
        config.get("arazzo") or [],
        (config.get("security") or {}).get("allowedRefRoots") or [],
    )
    destination = output_directory or str(Path("dist") / f"mock-{package_version}")
    package_path = write_mock_package(
        destination,
        package_version,
        generator_version(),
        documents,
        routes,
        sources.openapi,
        sources.arazzo,
        source_references=sources.provenance(),
    )
    print(f"Mock package created: {package_path}")
    return ExitCode.SUCCESS


def _start_mocks(config: dict) -> int:
    mock = config.get("mock") or {}
    bind_host = mock.get("bindHost")
    port = mock.get("port")
    if not isinstance(bind_host, str) or not bind_host or not isinstance(port, int):
        raise ToolError(
            "CONFIG_INVALID",
            "start-mocks requires explicit mock.bindHost and integer mock.port.",
            ExitCode.CONFIGURATION_ERROR,
        )
    max_request_bytes = _positive_int(
        mock.get("maxRequestBytes", 10 * 1024 * 1024),
        "mock.maxRequestBytes",
    )
    try:
        server = create_mock_server(
            bind_host,
            port,
            _mock_routes(config),
            validate_requests=(config.get("tests") or {}).get("validateRequests", True)
            is True,
            max_request_bytes=max_request_bytes,
        )
    except OSError as error:
        raise ToolError(
            "MOCK_SERVER_START_FAILED",
            f"Unable to bind mock server to {bind_host}:{port}: {error}.",
            ExitCode.CONFIGURATION_ERROR,
        ) from error
    print(
        f"Mock server listening on http://{bind_host}:{server.server_port}", flush=True
    )
    serve_mock_server(server)
    return ExitCode.SUCCESS


def _start_mock_package(
    package_directory: str,
    bind_host_override: str | None,
    port_override: int | None,
) -> int:
    manifest, routes = load_mock_package(package_directory)
    bind_host = bind_host_override if bind_host_override is not None else "127.0.0.1"
    port = 8080 if port_override is None else port_override
    if not bind_host or not 0 <= port <= 65535:
        raise ToolError(
            "CONFIG_INVALID",
            "Package runtime requires a non-empty bind host and port from 0 through 65535.",
            ExitCode.CONFIGURATION_ERROR,
        )
    try:
        server = create_mock_server(bind_host, port, routes, validate_requests=True)
    except OSError as error:
        raise ToolError(
            "MOCK_SERVER_START_FAILED",
            f"Unable to bind mock server to {bind_host}:{port}: {error}.",
            ExitCode.CONFIGURATION_ERROR,
        ) from error
    print(
        f"Mock package {manifest['packageVersion']} listening on "
        f"http://{bind_host}:{server.server_port}",
        flush=True,
    )
    serve_mock_server(server)
    return ExitCode.SUCCESS


def _stop_mocks() -> int:
    print(
        "Mock server uses foreground lifecycle; stop its start-mocks process with Ctrl+C."
    )
    return ExitCode.SUCCESS


def _run_tests(config: dict, *, report_only: bool = False) -> int:
    with contextlib.redirect_stdout(io.StringIO()):
        _validate_all(config)
    network = config.get("network") or {}
    timeouts = config.get("timeouts") or {}
    policy = NetworkPolicy(
        frozenset(),
        frozenset(),
        request_timeout_seconds=_duration_seconds(
            timeouts.get("request", "5s"), "timeouts.request"
        ),
        redirect_limit=_non_negative_int(
            network.get("redirectLimit", 3), "network.redirectLimit"
        ),
        max_response_bytes=_positive_int(
            network.get("maxResponseBytes", 10 * 1024 * 1024),
            "network.maxResponseBytes",
        ),
    )
    results = run_scenarios(
        config,
        policy,
        workflow_timeout_seconds=_duration_seconds(
            timeouts.get("workflow", "60s"), "timeouts.workflow"
        ),
    )
    reporting = config.get("report") or {}
    formats = reporting.get("formats", ["console"] if report_only else [])
    if not isinstance(formats, list):
        raise ToolError(
            "REPORT_CONFIG_INVALID",
            "report.formats must be a list.",
            ExitCode.CONFIGURATION_ERROR,
        )
    if formats:
        written = write_reports(results, formats, reporting.get("path"))
        if "console" in formats:
            print(render_console(results))
        elif not report_only:
            print(scenario_json(results))
        if report_only:
            for fmt, path in written.items():
                print(f"{fmt}: {path}")
    else:
        print(scenario_json(results))
    return (
        ExitCode.SUCCESS
        if all(result.passed for result in results)
        else ExitCode.TEST_ERROR
    )


def run(arguments: list[str]) -> int:
    args = parser().parse_args(arguments)
    if args.command is None:
        parser().print_help()
        return ExitCode.SUCCESS

    if args.command == "start-mocks" and args.package_dir:
        if args.config != "tool.yaml" or args.output:
            raise ToolError(
                "CONFIG_INVALID",
                "Package startup uses --package-dir and cannot be combined with --config or --output.",
                ExitCode.CONFIGURATION_ERROR,
            )
        return _start_mock_package(args.package_dir, args.bind_host, args.port)
    if args.command != "start-mocks" and (
        args.package_dir or args.bind_host is not None or args.port is not None
    ):
        raise ToolError(
            "CONFIG_INVALID",
            "--package-dir, --bind-host, and --port are only valid for start-mocks.",
            ExitCode.CONFIGURATION_ERROR,
        )
    config = load_config(args.config)

    if args.command == "validate-openapi":
        return _validate_openapi(config)
    if args.command == "validate-arazzo":
        return _validate_arazzo(config)
    if args.command == "validate-all":
        return _validate_all(config)
    if args.command == "list-workflows":
        return _list_workflows(config)
    if args.command == "run-workflow":
        return _run_workflow(config, args.workflow, args.input)
    if args.command == "generate-mocks":
        return _generate_mocks(config, args.output)
    if args.command == "start-mocks":
        return _start_mocks(config)
    if args.command == "stop-mocks":
        return _stop_mocks()
    if args.command == "run-tests":
        return _run_tests(config)
    if args.command == "report":
        return _run_tests(config, report_only=True)

    raise ToolError(
        "COMMAND_NOT_IMPLEMENTED",
        f"{args.command} is not implemented yet.",
    )


def main() -> int:
    try:
        return run(sys.argv[1:])
    except ToolError as error:
        print(error, file=sys.stderr)
        return error.exit_code
    except Exception as error:
        print(f"INTERNAL_ERROR: {error}", file=sys.stderr)
        return ExitCode.INTERNAL_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
