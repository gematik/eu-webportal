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

from tools.openapi_arazzo_tool.openapi.examples import find_example_issues
from tools.openapi_arazzo_tool.openapi.loader import load_openapi_document

FIXTURES = Path(__file__).parent / "fixtures" / "openapi"


class OpenApiExampleValidationTest(unittest.TestCase):
    def test_accepts_inline_named_and_external_examples_without_loading_external_value(
        self,
    ) -> None:
        document = load_openapi_document(
            str(FIXTURES / "valid" / "valid-examples.yaml")
        )

        self.assertEqual(find_example_issues(document), [])

    def test_collects_invalid_example_definition_issues(self) -> None:
        document = load_openapi_document(
            str(FIXTURES / "invalid" / "invalid-examples.yaml")
        )

        issues = find_example_issues(document)

        self.assertEqual(len(issues), 5)
        self.assertTrue(
            all(issue.code == "OPENAPI_EXAMPLE_INVALID" for issue in issues)
        )
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("$.components.examples.BothValues", messages)
        self.assertIn("$.components.examples.Scalar", messages)
        self.assertIn("$.components.parameters.BadExamples.examples", messages)
        self.assertIn(
            "$.paths./widgets.post.requestBody.content.application/json", messages
        )
        self.assertIn("$.paths./widgets.post.responses.201.headers.Location", messages)
