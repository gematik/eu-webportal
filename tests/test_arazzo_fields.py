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

from tools.openapi_arazzo_tool.arazzo.fields import find_field_issues
from tools.openapi_arazzo_tool.arazzo.loader import load_arazzo_document

FIXTURES = Path(__file__).parent / "fixtures" / "arazzo"


class ArazzoFieldValidationTest(unittest.TestCase):
    def test_accepts_supported_fields_and_extensions(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "valid" / "valid-step-inputs.yaml")
        )

        self.assertEqual(find_field_issues(document), [])

    def test_rejects_unknown_and_known_unsupported_fields(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "invalid-fields.yaml")
        )

        issues = find_field_issues(document)

        self.assertEqual(len(issues), 11)
        self.assertEqual(
            [issue.code for issue in issues].count("ARAZZO_STRUCTURE_INVALID"),
            9,
        )
        self.assertEqual(
            [issue.code for issue in issues].count("ARAZZO_FEATURE_UNSUPPORTED"),
            2,
        )
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("Unknown Arazzo field 'unknownRoot'", messages)
        self.assertIn("Unknown Arazzo field 'unknownAction'", messages)
        self.assertIn("Arazzo $self base URIs are not supported", messages)
        self.assertIn("Request body payload replacements are not supported", messages)
        self.assertNotIn("x-root-extension", messages)
        self.assertNotIn("x-workflow-extension", messages)
