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

import tempfile
import unittest
from pathlib import Path

from tools.openapi_arazzo_tool.arazzo.loader import load_arazzo_document
from tools.openapi_arazzo_tool.arazzo.model import ArazzoDocument
from tools.openapi_arazzo_tool.cross_validation.sources import (
    find_source_issues,
    resolve_sources,
)

FIXTURES = Path(__file__).parent / "fixtures" / "cross"


class ArazzoSourceValidationTest(unittest.TestCase):
    def test_accepts_local_valid_openapi_source(self) -> None:
        document = load_arazzo_document(str(FIXTURES / "valid" / "workflow.yaml"))

        self.assertEqual(find_source_issues(document, [str(FIXTURES)]), [])

    def test_rejects_missing_source(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "missing-source.yaml")
        )

        issues = find_source_issues(document, [str(FIXTURES)])

        self.assertEqual([issue.code for issue in issues], ["ARAZZO_SOURCE_UNRESOLVED"])

    def test_rejects_remote_source_without_network_access(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "remote-source.yaml")
        )

        issues = find_source_issues(document, [str(FIXTURES)])

        self.assertEqual([issue.code for issue in issues], ["ARAZZO_SOURCE_FORBIDDEN"])

    def test_rejects_invalid_referenced_openapi_document(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "invalid-source.yaml")
        )

        issues = find_source_issues(document, [str(FIXTURES)])

        self.assertEqual([issue.code for issue in issues], ["ARAZZO_SOURCE_UNRESOLVED"])

    def test_rejects_non_mapping_source_and_keeps_other_valid_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "invalid.yaml").write_text("- not a mapping\n", encoding="utf-8")
            (root / "valid.yaml").write_text(
                "openapi: 3.1.0\n"
                "info:\n"
                "  title: Valid source\n"
                "  version: 1.0.0\n"
                "paths: {}\n",
                encoding="utf-8",
            )
            document = ArazzoDocument(
                str(root / "workflow.yaml"),
                "1.1.0",
                {
                    "sourceDescriptions": [
                        {"name": "invalid", "url": "invalid.yaml", "type": "openapi"},
                        {"name": "valid", "url": "valid.yaml", "type": "openapi"},
                    ]
                },
            )

            resolved = resolve_sources(document, [directory])

        self.assertEqual(set(resolved.sources), {"valid"})
        self.assertEqual(
            [issue.code for issue in resolved.issues], ["ARAZZO_SOURCE_UNRESOLVED"]
        )
        self.assertIn("root must be a mapping", resolved.issues[0].message)
