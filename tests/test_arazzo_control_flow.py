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

from tools.openapi_arazzo_tool.arazzo.control_flow import find_control_flow_issues
from tools.openapi_arazzo_tool.arazzo.loader import load_arazzo_document

FIXTURES = Path(__file__).parent / "fixtures" / "arazzo"


class ArazzoControlFlowValidationTest(unittest.TestCase):
    def test_accepts_non_cyclic_unconditional_goto(self) -> None:
        document = load_arazzo_document(str(FIXTURES / "valid" / "valid-actions.yaml"))

        self.assertEqual(find_control_flow_issues(document), [])

    def test_rejects_unconditional_step_and_workflow_cycles(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "invalid-control-flow.yaml")
        )

        issues = find_control_flow_issues(document)

        self.assertEqual(len(issues), 3)
        self.assertTrue(
            all(issue.code == "ARAZZO_CONTROL_FLOW_CYCLE" for issue in issues)
        )
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("$.workflows[0].steps[0]", messages)
        self.assertIn("$.workflows[1].steps[0]", messages)
        self.assertIn("$.workflows[2].steps[0]", messages)
