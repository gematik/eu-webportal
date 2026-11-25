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
from tools.openapi_arazzo_tool.openapi.responses import find_response_issues

FIXTURES = Path(__file__).parent / "fixtures" / "openapi"


class OpenApiResponseValidationTest(unittest.TestCase):
    def test_accepts_explicit_range_and_default_responses(self) -> None:
        document = load_openapi_document(
            str(FIXTURES / "valid" / "valid-responses.yaml")
        )

        self.assertEqual(find_response_issues(document), [])

    def test_collects_invalid_response_definition_issues(self) -> None:
        document = load_openapi_document(
            str(FIXTURES / "invalid" / "invalid-responses.yaml")
        )

        issues = find_response_issues(document)

        self.assertEqual(len(issues), 8)
        self.assertTrue(
            all(issue.code == "OPENAPI_RESPONSE_INVALID" for issue in issues)
        )
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("$.components.responses.MissingDescription.description", messages)
        self.assertIn("$.components.responses.MissingDescription.headers", messages)
        self.assertIn("$.paths./widgets.get.responses.999", messages)
        self.assertIn("$.paths./widgets.get.responses.200", messages)
        self.assertIn("$.paths./widgets.get.responses.default.description", messages)
        self.assertIn("$.paths./widgets.get.responses.default.content", messages)
        self.assertIn("$.paths./widgets.get.responses.400", messages)
        self.assertIn("$.paths./empty.get.responses", messages)
