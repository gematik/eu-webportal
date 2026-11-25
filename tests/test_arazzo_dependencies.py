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

from tools.openapi_arazzo_tool.arazzo.dependencies import find_dependency_issues
from tools.openapi_arazzo_tool.arazzo.loader import load_arazzo_document

FIXTURES = Path(__file__).parent / "fixtures" / "arazzo"


class ArazzoDependencyValidationTest(unittest.TestCase):
    def test_accepts_existing_workflow_and_preceding_step_dependencies(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "valid" / "valid-dependencies.yaml")
        )

        self.assertEqual(find_dependency_issues(document), [])

    def test_rejects_invalid_self_unknown_duplicate_and_forward_dependencies(
        self,
    ) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "invalid-dependencies.yaml")
        )

        issues = find_dependency_issues(document)

        self.assertEqual(len(issues), 8)
        self.assertTrue(
            all(issue.code == "ARAZZO_DEPENDENCY_INVALID" for issue in issues)
        )
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("Workflow must not depend on itself", messages)
        self.assertIn("Referenced workflow 'missing' does not exist", messages)
        self.assertIn("Dependency 'missing' must be unique", messages)
        self.assertIn("Dependency must be a non-empty string", messages)
        self.assertIn("$.workflows[0].steps[0].dependsOn", messages)
        self.assertIn(
            "Step dependency 'missing' must reference a preceding step", messages
        )
        self.assertIn(
            "Step dependency 'read' must reference a preceding step", messages
        )
        self.assertIn("Dependency 'create' must be unique", messages)
