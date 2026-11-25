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

import unittest
from pathlib import Path

from tools.openapi_arazzo_tool.arazzo.inputs import find_input_issues
from tools.openapi_arazzo_tool.arazzo.loader import load_arazzo_document

FIXTURES = Path(__file__).parent / "fixtures" / "arazzo"


class ArazzoInputValidationTest(unittest.TestCase):
    def test_accepts_step_parameters_and_request_body(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "valid" / "valid-step-inputs.yaml")
        )

        self.assertEqual(find_input_issues(document), [])

    def test_collects_invalid_step_input_issues(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "invalid-step-inputs.yaml")
        )

        issues = find_input_issues(document)

        self.assertEqual(len(issues), 8)
        self.assertTrue(all(issue.code == "ARAZZO_INPUT_INVALID" for issue in issues))
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("$.workflows[0].steps[0].parameters[0].name", messages)
        self.assertIn("$.workflows[0].steps[0].parameters[0]", messages)
        self.assertIn("$.workflows[0].steps[0].parameters[1].in", messages)
        self.assertIn("Step parameter 'duplicate' in 'query' must be unique", messages)
        self.assertIn("$.workflows[0].steps[0].requestBody.contentType", messages)
        self.assertIn("$.workflows[0].steps[0].requestBody", messages)
        self.assertIn("$.workflows[0].steps[1].parameters", messages)
        self.assertIn("$.workflows[0].steps[2].requestBody", messages)

    def test_collects_invalid_workflow_input_schema_issues(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "invalid-workflow-inputs.yaml")
        )

        issues = find_input_issues(document)

        self.assertEqual(len(issues), 2)
        self.assertTrue(all(issue.code == "ARAZZO_INPUT_INVALID" for issue in issues))
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("$.workflows[0].inputs", messages)
        self.assertIn("Workflow inputs must be a JSON Schema mapping", messages)
        self.assertIn("$.workflows[1].inputs", messages)
        self.assertIn(
            "Workflow inputs must be a valid JSON Schema 2020-12 object", messages
        )

    def test_rejects_reusable_parameter_objects_outside_v1(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "unsupported-reusable-features.yaml")
        )

        issues = find_input_issues(document)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].code, "ARAZZO_FEATURE_UNSUPPORTED")
        self.assertIn("$.workflows[0].steps[0].parameters[0].$ref", issues[0].message)
