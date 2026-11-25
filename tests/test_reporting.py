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

import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from tools.openapi_arazzo_tool.arazzo.runner import StepResult, WorkflowResult
from tools.openapi_arazzo_tool.errors import ToolError
from tools.openapi_arazzo_tool.reporting import (
    render_console,
    render_html,
    render_json,
    render_junit,
    write_reports,
)
from tools.openapi_arazzo_tool.scenarios import ScenarioResult


class ReportingTest(unittest.TestCase):
    def setUp(self) -> None:
        step = StepResult(
            "read",
            False,
            404,
            operation="api.read",
            method="GET",
            url="https://example.test/<script>alert(1)</script>",
            duration_ms=12.5,
            assertion="$statusCode == 200",
            expected="200",
            actual="404",
            openapi_source="api.yaml#/widgets",
            arazzo_source="workflow.yaml#read",
        )
        self.results = (
            ScenarioResult(
                "bad<script>.yaml",
                False,
                WorkflowResult("read-widget", False, {}, (step,)),
                mock_scenario=("not-found",),
            ),
            ScenarioResult("error.yaml", False, None, "Unexpected <value>"),
        )

    def test_json_includes_traceable_step_without_credentials(self) -> None:
        record = json.loads(render_json(self.results))["scenarios"][0]
        self.assertEqual(record["mockScenario"], ["not-found"])
        self.assertEqual(record["steps"][0]["operation"], "api.read")
        self.assertEqual(record["steps"][0]["openapiSource"], "api.yaml#/widgets")
        self.assertIn("FAIL", render_console(self.results))

    def test_junit_is_well_formed_and_counts_failures(self) -> None:
        suite = ET.fromstring(render_junit(self.results))
        self.assertEqual(suite.attrib["tests"], "2")
        self.assertEqual(suite.attrib["failures"], "2")
        self.assertEqual(len(suite.findall(".//failure")), 2)

    def test_html_escapes_user_values_and_disables_scripts(self) -> None:
        page = render_html(self.results)
        self.assertIn("default-src 'none'", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertNotIn("<script>", page)

    def test_writes_configured_files_and_rejects_missing_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            written = write_reports(
                self.results, ["console", "json", "junit", "html"], directory
            )
            self.assertEqual(set(written), {"json", "junit", "html"})
            self.assertTrue(all(Path(path).is_file() for path in written.values()))
        with self.assertRaises(ToolError):
            write_reports(self.results, ["json"], None)
