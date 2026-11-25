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

from tools.openapi_arazzo_tool.openapi.loader import load_openapi_document
from tools.openapi_arazzo_tool.openapi.request_bodies import find_request_body_issues

FIXTURES = Path(__file__).parent / "fixtures" / "openapi"


class OpenApiRequestBodyValidationTest(unittest.TestCase):
    def test_accepts_reusable_and_operation_request_bodies(self) -> None:
        document = load_openapi_document(
            str(FIXTURES / "valid" / "valid-request-bodies.yaml")
        )

        self.assertEqual(find_request_body_issues(document), [])

    def test_collects_invalid_request_body_issues(self) -> None:
        document = load_openapi_document(
            str(FIXTURES / "invalid" / "invalid-request-bodies.yaml")
        )

        issues = find_request_body_issues(document)

        self.assertEqual(len(issues), 5)
        self.assertTrue(
            all(issue.code == "OPENAPI_REQUEST_BODY_INVALID" for issue in issues)
        )
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("$.components.requestBodies.MissingContent.content", messages)
        self.assertIn("$.components.requestBodies.EmptyContent.content", messages)
        self.assertIn("$.paths./widgets.post.requestBody.required", messages)
        self.assertIn(
            "$.paths./widgets.post.requestBody.content.application/json", messages
        )
        self.assertIn("$.paths./invalid.post.requestBody", messages)
