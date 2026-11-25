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

from tools.openapi_arazzo_tool.arazzo.loader import load_arazzo_document
from tools.openapi_arazzo_tool.arazzo.outputs import find_output_issues

FIXTURES = Path(__file__).parent / "fixtures" / "arazzo"


class ArazzoOutputValidationTest(unittest.TestCase):
    def test_accepts_step_and_workflow_outputs_with_success_criteria(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "valid" / "valid-outputs-and-criteria.yaml")
        )

        self.assertEqual(find_output_issues(document), [])

    def test_collects_invalid_output_and_success_criteria_issues(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "invalid-outputs-and-criteria.yaml")
        )

        issues = find_output_issues(document)

        self.assertEqual(len(issues), 9)
        self.assertTrue(all(issue.code == "ARAZZO_OUTPUT_INVALID" for issue in issues))
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("$.workflows[0].outputs", messages)
        self.assertIn("$.workflows[0].steps[0].outputs.", messages)
        self.assertIn("$.workflows[0].steps[0].successCriteria", messages)
        self.assertIn("$.workflows[0].steps[1].successCriteria[0]", messages)
        self.assertIn("$.workflows[0].steps[1].successCriteria[1].condition", messages)
        self.assertIn("$.workflows[0].steps[2].outputs", messages)
        self.assertIn("$.workflows[0].steps[2].successCriteria", messages)
        self.assertIn("$.workflows[0].steps[3].outputs.invalid output", messages)
        self.assertIn("Output names may contain only letters", messages)

    def test_rejects_selector_objects_outside_v1(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "unsupported-reusable-features.yaml")
        )

        issues = find_output_issues(document)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].code, "ARAZZO_FEATURE_UNSUPPORTED")
        self.assertIn("$.workflows[0].steps[0].outputs.widget", issues[0].message)
