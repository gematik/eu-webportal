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
from tools.openapi_arazzo_tool.openapi.structure import find_structure_issues

FIXTURES = Path(__file__).parent / "fixtures" / "openapi"


class OpenApiStructureValidationTest(unittest.TestCase):
    def test_accepts_minimal_valid_document(self) -> None:
        document = load_openapi_document(str(FIXTURES / "valid" / "minimal-3.1.yaml"))

        self.assertEqual(find_structure_issues(document), [])

    def test_collects_basic_document_structure_issues(self) -> None:
        document = load_openapi_document(
            str(FIXTURES / "invalid" / "invalid-document-structure.yaml")
        )

        issues = find_structure_issues(document)

        self.assertEqual(len(issues), 5)
        self.assertTrue(
            all(issue.code == "OPENAPI_STRUCTURE_INVALID" for issue in issues)
        )
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("$.info.title", messages)
        self.assertIn("$.info.version", messages)
        self.assertIn("$.paths.ping", messages)
        self.assertIn("$.paths./not-a-path-item", messages)
        self.assertIn("$.components", messages)
