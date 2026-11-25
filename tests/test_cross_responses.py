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
from tools.openapi_arazzo_tool.cross_validation.responses import (
    find_response_reference_issues,
)
from tools.openapi_arazzo_tool.cross_validation.sources import resolve_sources

FIXTURES = Path(__file__).parent / "fixtures" / "cross"


class ArazzoResponseReferenceValidationTest(unittest.TestCase):
    def test_accepts_defined_status_headers_and_body_paths(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "valid" / "response-workflow.yaml")
        )
        sources = resolve_sources(document, [str(FIXTURES)])

        self.assertEqual(find_response_reference_issues(document, sources), [])

    def test_rejects_unknown_status_headers_and_body_paths(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "invalid-response-references.yaml")
        )
        sources = resolve_sources(document, [str(FIXTURES)])

        issues = find_response_reference_issues(document, sources)

        self.assertEqual(len(issues), 4)
        self.assertTrue(
            all(issue.code == "ARAZZO_RESPONSE_REFERENCE_INVALID" for issue in issues)
        )
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("status code '202'", messages)
        self.assertIn("status code '404'", messages)
        self.assertIn("header 'X-Missing'", messages)
        self.assertIn("body path '#/missing'", messages)
