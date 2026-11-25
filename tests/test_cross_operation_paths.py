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
from tools.openapi_arazzo_tool.cross_validation.operation_paths import (
    find_operation_path_issues,
)
from tools.openapi_arazzo_tool.cross_validation.sources import resolve_sources

FIXTURES = Path(__file__).parent / "fixtures" / "cross"


class ArazzoOperationPathValidationTest(unittest.TestCase):
    def test_accepts_existing_scoped_openapi_operation_pointer(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "valid" / "operation-path-workflow.yaml")
        )
        sources = resolve_sources(document, [str(FIXTURES)])

        self.assertEqual(sources.issues, [])
        self.assertEqual(find_operation_path_issues(document, sources), [])

    def test_rejects_invalid_operation_path_references(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "invalid-operation-path.yaml")
        )
        sources = resolve_sources(document, [str(FIXTURES)])

        issues = find_operation_path_issues(document, sources)

        self.assertEqual(len(issues), 4)
        self.assertTrue(
            all(issue.code == "ARAZZO_OPERATION_UNRESOLVED" for issue in issues)
        )
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("operationPath must use", messages)
        self.assertIn("Referenced source 'missing' does not exist", messages)
        self.assertIn("operationPath must point to", messages)
        self.assertIn("does not resolve in source 'widgets'", messages)
