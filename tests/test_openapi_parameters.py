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
from tools.openapi_arazzo_tool.openapi.parameters import find_parameter_issues

FIXTURES = Path(__file__).parent / "fixtures" / "openapi"


class OpenApiParameterValidationTest(unittest.TestCase):
    def test_accepts_valid_inline_and_reusable_parameters(self) -> None:
        document = load_openapi_document(
            str(FIXTURES / "valid" / "valid-parameters.yaml")
        )

        self.assertEqual(find_parameter_issues(document), [])

    def test_collects_parameter_definition_and_template_issues(self) -> None:
        document = load_openapi_document(
            str(FIXTURES / "invalid" / "invalid-parameters.yaml")
        )

        issues = find_parameter_issues(document)

        self.assertEqual(len(issues), 7)
        self.assertTrue(
            all(issue.code == "OPENAPI_PARAMETER_INVALID" for issue in issues)
        )
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("$.components.parameters.MissingName.name", messages)
        self.assertIn("$.paths./widgets/{widgetId}.parameters[0].required", messages)
        self.assertIn("Duplicate parameter 'duplicate' in 'query'", messages)
        self.assertIn("$.paths./widgets/{widgetId}.get.parameters[0].in", messages)
        self.assertIn("exactly one of schema or content", messages)
        self.assertIn("Path template parameter 'identifier'", messages)
        self.assertIn("Path Parameter Object 'not-in-template'", messages)
