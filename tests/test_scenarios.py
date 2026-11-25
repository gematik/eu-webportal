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

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from tools.openapi_arazzo_tool.cli import run
from tools.openapi_arazzo_tool.errors import ToolError
from tools.openapi_arazzo_tool.http.execution import NetworkPolicy
from tools.openapi_arazzo_tool.scenarios import _load_scenario, run_scenarios


class ScenarioTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "api.yaml").write_text(
            """openapi: 3.1.0
info: {title: Widgets, version: 1.0.0}
paths:
  /widgets/{id}:
    get:
      operationId: getWidget
      parameters:
        - name: id
          in: path
          required: true
          schema: {type: string}
      responses:
        '200':
          description: Found
          content:
            application/json:
              example: {id: found}
        '404':
          description: Missing
          content:
            application/json:
              example: {id: missing}
""",
            encoding="utf-8",
        )
        (self.root / "workflow.yaml").write_text(
            """arazzo: 1.1.0
info: {title: Find widget, version: 1.0.0}
sourceDescriptions:
  - {name: api, url: ./api.yaml, type: openapi}
workflows:
  - workflowId: find-widget
    inputs:
      type: object
      required: [id]
      properties:
        id: {type: string}
    steps:
      - stepId: find
        operationId: getWidget
        parameters:
          - {name: id, in: path, value: $inputs.id}
""",
            encoding="utf-8",
        )
        self.cases = self.root / "cases"
        self.cases.mkdir()
        self.config: dict[str, Any] = {
            "openapi": [str(self.root / "api.yaml")],
            "arazzo": [str(self.root / "workflow.yaml")],
            "security": {"allowedRefRoots": [str(self.root)]},
            "tests": {"path": str(self.cases)},
            "mock": {"bindHost": "127.0.0.1", "port": 0},
            "scenarios": {"missing": {"getWidget": {"response": 404}}},
        }
        self.policy = NetworkPolicy(frozenset(), frozenset())

    def _write_case(self, name: str, value: dict) -> None:
        (self.cases / name).write_text(json.dumps(value), encoding="utf-8")

    def test_isolates_sequential_success_and_failure_scenarios(self) -> None:
        self._write_case(
            "a-missing.json",
            {
                "workflow": "find-widget",
                "inputs": {"id": "absent"},
                "mockScenario": {"getWidget": "missing"},
                "expect": {"workflow": "failure", "step": "find", "status": 404},
            },
        )
        self._write_case(
            "b-found.json",
            {
                "workflow": "find-widget",
                "inputs": {"id": "present"},
                "expect": {"workflow": "success", "step": "find", "status": 200},
            },
        )
        results = run_scenarios(self.config, self.policy, workflow_timeout_seconds=5)
        self.assertEqual(
            [result.name for result in results], ["a-missing.json", "b-found.json"]
        )
        self.assertTrue(all(result.passed for result in results), results)
        self.assertEqual(
            [
                result.workflow.steps[0].status_code
                for result in results
                if result.workflow is not None
            ],
            [404, 200],
        )

    def test_fail_fast_and_wrong_expectation(self) -> None:
        self._write_case(
            "a-wrong.json",
            {
                "workflow": "find-widget",
                "inputs": {"id": "present"},
                "expect": {"workflow": "failure"},
            },
        )
        self._write_case(
            "b-not-run.json",
            {
                "workflow": "find-widget",
                "inputs": {"id": "present"},
            },
        )
        self.config["tests"]["failFast"] = True
        results = run_scenarios(self.config, self.policy, workflow_timeout_seconds=5)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].passed)

    def test_rejects_scenario_environment_override(self) -> None:
        self._write_case(
            "unsafe.json",
            {
                "workflow": "find-widget",
                "environment": {"baseUrl": "http://internal.example"},
            },
        )
        with self.assertRaises(ToolError):
            _load_scenario(self.cases / "unsafe.json")

    def test_cli_runs_configured_scenarios(self) -> None:
        self._write_case(
            "found.json", {"workflow": "find-widget", "inputs": {"id": "present"}}
        )
        config_path = self.root / "tool.yaml"
        import yaml

        config_path.write_text(yaml.safe_dump(self.config), encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(run(["run-tests", "--config", str(config_path)]), 0)
        self.assertTrue(json.loads(output.getvalue())[0]["passed"])

    def test_report_command_writes_json_junit_and_html(self) -> None:
        self._write_case(
            "found.json", {"workflow": "find-widget", "inputs": {"id": "present"}}
        )
        self.config["report"] = {
            "formats": ["console", "json", "junit", "html"],
            "path": str(self.root / "reports"),
        }
        config_path = self.root / "tool.yaml"
        import yaml

        config_path.write_text(yaml.safe_dump(self.config), encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(run(["report", "--config", str(config_path)]), 0)
        self.assertIn("PASS found.json", output.getvalue())
        self.assertTrue((self.root / "reports" / "report.json").exists())
        self.assertTrue((self.root / "reports" / "report.xml").exists())
        self.assertTrue((self.root / "reports" / "report.html").exists())

    def test_401_mock_runs_without_exposing_credentials(self) -> None:
        api = self.root / "api.yaml"
        text = api.read_text(encoding="utf-8")
        text = text.replace(
            "paths:\n",
            "components:\n  securitySchemes:\n"
            "    token: {type: http, scheme: bearer}\npaths:\n",
        ).replace(
            "      responses:\n",
            "      security: [{token: []}]\n      responses:\n"
            "        '401': {description: Unauthorized}\n",
        )
        api.write_text(text, encoding="utf-8")
        self.config["scenarios"]["unauthorized"] = {"getWidget": {"response": 401}}
        self._write_case(
            "unauthorized.json",
            {
                "workflow": "find-widget",
                "inputs": {"id": "present"},
                "mockScenario": {"getWidget": "unauthorized"},
                "expect": {"workflow": "failure", "step": "find", "status": 401},
            },
        )
        result = run_scenarios(self.config, self.policy, workflow_timeout_seconds=5)
        self.assertTrue(result[0].passed, result)
        workflow = result[0].workflow
        if workflow is None:
            self.fail("Scenario did not return a workflow result.")
        self.assertEqual(workflow.steps[0].status_code, 401)
