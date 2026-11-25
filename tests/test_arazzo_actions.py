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

from tools.openapi_arazzo_tool.arazzo.actions import find_action_issues
from tools.openapi_arazzo_tool.arazzo.loader import load_arazzo_document

FIXTURES = Path(__file__).parent / "fixtures" / "arazzo"


class ArazzoActionValidationTest(unittest.TestCase):
    def test_accepts_supported_actions_and_resolved_goto_targets(self) -> None:
        document = load_arazzo_document(str(FIXTURES / "valid" / "valid-actions.yaml"))

        self.assertEqual(find_action_issues(document), [])

    def test_collects_invalid_actions_and_goto_targets(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "invalid-actions.yaml")
        )

        issues = find_action_issues(document)

        self.assertEqual(len(issues), 15)
        self.assertEqual(
            [issue.code for issue in issues].count("ARAZZO_FEATURE_UNSUPPORTED"),
            1,
        )
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("$.workflows[0].steps[0].onFailure", messages)
        self.assertIn("$.workflows[0].steps[1].onSuccess[0].name", messages)
        self.assertIn("$.workflows[0].steps[1].onSuccess[0].type", messages)
        self.assertIn("Action criteria must define at least one criterion", messages)
        self.assertIn("$.workflows[0].steps[1].onFailure[0].retryAfter", messages)
        self.assertIn("$.workflows[0].steps[1].onFailure[0].retryLimit", messages)
        self.assertIn("goto action must define exactly one", messages)
        self.assertIn("goto step target 'absent' does not exist", messages)
        self.assertIn("end action must not define retryLimit", messages)
        self.assertIn("Action type must be one of end, goto", messages)
        self.assertIn("Action parameters are not supported in V1", messages)
        self.assertIn("goto action must not define retryLimit", messages)
        self.assertIn("Action name 'action-parameters' must be unique", messages)

    def test_rejects_reusable_action_objects_outside_v1(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "unsupported-reusable-features.yaml")
        )

        issues = find_action_issues(document)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].code, "ARAZZO_FEATURE_UNSUPPORTED")
        self.assertIn("$.workflows[0].steps[0].onFailure[0].$ref", issues[0].message)
