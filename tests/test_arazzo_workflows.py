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
from tools.openapi_arazzo_tool.arazzo.workflows import find_workflow_issues

FIXTURES = Path(__file__).parent / "fixtures" / "arazzo"


class ArazzoWorkflowValidationTest(unittest.TestCase):
    def test_accepts_unique_workflow_and_step_ids_with_operation_id(self) -> None:
        document = load_arazzo_document(str(FIXTURES / "valid" / "minimal-1.1.yaml"))

        self.assertEqual(find_workflow_issues(document), [])

    def test_accepts_non_negative_step_timeout(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "valid" / "valid-step-timeout.yaml")
        )

        self.assertEqual(find_workflow_issues(document), [])

    def test_collects_workflow_step_and_unsupported_feature_issues(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "invalid-workflows.yaml")
        )

        issues = find_workflow_issues(document)

        self.assertEqual(len(issues), 14)
        self.assertEqual(
            [issue.code for issue in issues].count("ARAZZO_FEATURE_UNSUPPORTED"),
            4,
        )
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("Step ID 'duplicate-step' must be unique", messages)
        self.assertIn("exactly one of operationId or operationPath", messages)
        self.assertIn("operationRef is not supported in V1", messages)
        self.assertIn(
            "AsyncAPI channelPath references is not supported in V1", messages
        )
        self.assertIn("AsyncAPI step actions is not supported in V1", messages)
        self.assertIn("workflow invocation steps is not supported in V1", messages)
        self.assertIn("Workflow ID 'duplicate' must be unique", messages)
        self.assertIn("$.workflows[1].steps", messages)
        self.assertIn("$.workflows[2].workflowId", messages)

    def test_rejects_workflow_features_outside_v1(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "unsupported-workflow-features.yaml")
        )

        issues = find_workflow_issues(document)

        self.assertEqual(len(issues), 3)
        self.assertTrue(
            all(issue.code == "ARAZZO_FEATURE_UNSUPPORTED" for issue in issues)
        )
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("$.workflows[0].parameters", messages)
        self.assertIn("$.workflows[0].successActions", messages)
        self.assertIn("$.workflows[0].failureActions", messages)

    def test_rejects_invalid_timeouts_and_async_only_correlation_id(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "invalid-step-timeout.yaml")
        )

        issues = find_workflow_issues(document)

        self.assertEqual(len(issues), 4)
        self.assertEqual(
            [issue.code for issue in issues].count("ARAZZO_FEATURE_UNSUPPORTED"),
            1,
        )
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("$.workflows[0].steps[0].timeout", messages)
        self.assertIn("$.workflows[0].steps[1].timeout", messages)
        self.assertIn("$.workflows[0].steps[2].timeout", messages)
        self.assertIn(
            "AsyncAPI correlation identifiers is not supported in V1", messages
        )
