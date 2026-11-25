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
from tools.openapi_arazzo_tool.arazzo.references import (
    find_step_output_reference_issues,
)

FIXTURES = Path(__file__).parent / "fixtures" / "arazzo"


class ArazzoStepOutputReferenceValidationTest(unittest.TestCase):
    def test_accepts_resolved_prior_step_outputs_and_workflow_outputs(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "valid" / "valid-step-output-references.yaml")
        )

        self.assertEqual(find_step_output_reference_issues(document), [])

    def test_rejects_unknown_forward_and_missing_step_outputs(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "invalid-step-output-references.yaml")
        )

        issues = find_step_output_reference_issues(document)

        self.assertEqual(len(issues), 3)
        self.assertTrue(
            all(issue.code == "ARAZZO_EXPRESSION_UNRESOLVED" for issue in issues)
        )
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("Referenced step 'missing' does not exist", messages)
        self.assertIn("step 'read' is a forward reference", messages)
        self.assertIn(
            "Referenced output 'missing' does not exist on step 'create'", messages
        )
