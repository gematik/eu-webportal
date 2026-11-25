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

"""Redacted, deterministic scenario reports."""

import html
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .errors import ExitCode, ToolError
from .scenarios import ScenarioResult

_FORMATS = frozenset({"console", "json", "junit", "html"})


def report_records(results: tuple[ScenarioResult, ...]) -> list[dict[str, Any]]:
    """Build report data without request bodies, credentials, or workflow inputs."""
    return [
        {
            "scenario": result.name,
            "mockScenario": list(result.mock_scenario),
            "workflowId": result.workflow.workflow_id if result.workflow else None,
            "passed": result.passed,
            "error": result.error,
            "steps": [
                {
                    "stepId": step.step_id,
                    "operation": step.operation,
                    "method": step.method,
                    "url": step.url,
                    "durationMs": step.duration_ms,
                    "statusCode": step.status_code,
                    "assertion": step.assertion,
                    "expected": step.expected,
                    "actual": step.actual,
                    "passed": step.success,
                    "openapiSource": step.openapi_source,
                    "arazzoSource": step.arazzo_source,
                }
                for step in result.workflow.steps
            ]
            if result.workflow
            else [],
        }
        for result in results
    ]


def render_console(results: tuple[ScenarioResult, ...]) -> str:
    """Show compact workflow and step outcomes."""
    lines = []
    for item in report_records(results):
        lines.append(
            f"{'PASS' if item['passed'] else 'FAIL'} {item['scenario']} ({item['workflowId'] or 'unknown'})"
        )
        for step in item["steps"]:
            lines.append(
                f"  {'PASS' if step['passed'] else 'FAIL'} {step['stepId']} "
                f"{step['method']} {step['url']} {step['statusCode']} ({step['durationMs']}ms)"
            )
        if item["error"]:
            lines.append(f"  ERROR {item['error']}")
    return "\n".join(lines)


def render_json(results: tuple[ScenarioResult, ...]) -> str:
    """Serialize a stable JSON report."""
    return json.dumps(
        {"scenarios": report_records(results)},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def render_junit(results: tuple[ScenarioResult, ...]) -> str:
    """Generate one JUnit testcase per scenario."""
    suite = ET.Element(
        "testsuite",
        {
            "name": "openapi-arazzo",
            "tests": str(len(results)),
            "failures": str(sum(not item.passed for item in results)),
        },
    )
    for item in report_records(results):
        case = ET.SubElement(
            suite,
            "testcase",
            {
                "classname": item["workflowId"] or "unknown",
                "name": item["scenario"],
                "time": str(sum(step["durationMs"] for step in item["steps"]) / 1000),
            },
        )
        if not item["passed"]:
            details = (
                item["error"] or "Workflow outcome differs from scenario expectation."
            )
            ET.SubElement(case, "failure", {"message": details}).text = details
    return ET.tostring(suite, encoding="unicode")


def render_html(results: tuple[ScenarioResult, ...]) -> str:
    """Generate escaped, script-free HTML with a restrictive CSP."""
    lines = [
        '<!doctype html><html><head><meta charset="utf-8">',
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        "style-src 'none'; img-src 'none'; form-action 'none'; base-uri 'none'\">",
        "<title>Workflow report</title></head><body><h1>Workflow report</h1>",
    ]
    for item in report_records(results):
        lines.append(
            f"<section><h2>{'PASS' if item['passed'] else 'FAIL'} "
            f"{html.escape(item['scenario'])}</h2>"
        )
        for step in item["steps"]:
            lines.append(
                "<p>"
                + html.escape(
                    f"{step['stepId']} {step['method']} {step['url']} "
                    f"{step['statusCode']} {step['assertion']}"
                )
                + "</p>"
            )
        if item["error"]:
            lines.append(f"<p>{html.escape(item['error'])}</p>")
        lines.append("</section>")
    return "".join(lines + ["</body></html>"])


def write_reports(
    results: tuple[ScenarioResult, ...],
    formats: list[str],
    directory: str | None,
) -> dict[str, Path]:
    """Write requested reports only to a configured output directory."""
    if not formats or any(fmt not in _FORMATS for fmt in formats):
        raise ToolError(
            "REPORT_CONFIG_INVALID",
            "Unsupported or empty report formats.",
            ExitCode.CONFIGURATION_ERROR,
        )
    artifacts = [fmt for fmt in formats if fmt != "console"]
    if artifacts and not directory:
        raise ToolError(
            "REPORT_CONFIG_INVALID",
            "report.path is required for report files.",
            ExitCode.CONFIGURATION_ERROR,
        )
    if not artifacts:
        return {}
    if directory is None:
        raise ToolError(
            "REPORT_CONFIG_INVALID",
            "report.path is required for report files.",
            ExitCode.CONFIGURATION_ERROR,
        )
    root = Path(directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    renderers = {
        "json": (render_json, "report.json"),
        "junit": (render_junit, "report.xml"),
        "html": (render_html, "report.html"),
    }
    written: dict[str, Path] = {}
    for fmt in artifacts:
        render, name = renderers[fmt]
        path = root / name
        path.write_text(render(results), encoding="utf-8")
        written[fmt] = path
    return written
