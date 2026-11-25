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
from tools.openapi_arazzo_tool.arazzo.structure import find_structure_issues

FIXTURES = Path(__file__).parent / "fixtures" / "arazzo"


class ArazzoStructureValidationTest(unittest.TestCase):
    def test_accepts_openapi_sources_and_extensions(self) -> None:
        document = load_arazzo_document(str(FIXTURES / "valid" / "minimal-1.1.yaml"))

        self.assertEqual(find_structure_issues(document), [])

    def test_collects_structure_and_unsupported_feature_issues(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "invalid-document-structure.yaml")
        )

        issues = find_structure_issues(document)

        self.assertEqual(len(issues), 8)
        self.assertEqual(
            [issue.code for issue in issues].count("ARAZZO_FEATURE_UNSUPPORTED"),
            2,
        )
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("$.info.title", messages)
        self.assertIn("$.info.version", messages)
        self.assertIn("name 'duplicate' must be unique", messages)
        self.assertIn("$.sourceDescriptions[1].url", messages)
        self.assertIn("type 'custom' is unknown", messages)
        self.assertIn("$.workflows", messages)

    def test_rejects_components_outside_the_v1_support_matrix(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "unsupported-reusable-features.yaml")
        )

        issues = find_structure_issues(document)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].code, "ARAZZO_FEATURE_UNSUPPORTED")
        self.assertIn("$.components", issues[0].message)
