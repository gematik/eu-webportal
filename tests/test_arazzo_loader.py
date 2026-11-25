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
from tools.openapi_arazzo_tool.errors import ExitCode, ToolError

FIXTURES = Path(__file__).parent / "fixtures" / "arazzo"


class ArazzoLoaderTest(unittest.TestCase):
    def test_loads_valid_arazzo_11_document(self) -> None:
        document = load_arazzo_document(str(FIXTURES / "valid" / "minimal-1.1.yaml"))

        self.assertEqual(document.version, "1.1.0")
        self.assertEqual(document.raw["info"]["title"], "Minimal Valid Workflow")

    def test_rejects_arazzo_10(self) -> None:
        with self.assertRaises(ToolError) as context:
            load_arazzo_document(str(FIXTURES / "invalid" / "version-1.0.yaml"))

        self.assertEqual(context.exception.code, "ARAZZO_VERSION_UNSUPPORTED")
        self.assertEqual(context.exception.exit_code, ExitCode.VALIDATION_ERROR)

    def test_rejects_arazzo_12(self) -> None:
        with self.assertRaises(ToolError) as context:
            load_arazzo_document(str(FIXTURES / "invalid" / "version-1.2.yaml"))

        self.assertEqual(context.exception.code, "ARAZZO_VERSION_UNSUPPORTED")

    def test_rejects_broken_syntax(self) -> None:
        with self.assertRaises(ToolError) as context:
            load_arazzo_document(str(FIXTURES / "invalid" / "broken-syntax.yaml"))

        self.assertEqual(context.exception.code, "ARAZZO_SYNTAX_INVALID")

    def test_rejects_non_mapping_root(self) -> None:
        with self.assertRaises(ToolError) as context:
            load_arazzo_document(str(FIXTURES / "invalid" / "non-mapping-root.yaml"))

        self.assertEqual(context.exception.code, "ARAZZO_SYNTAX_INVALID")

    def test_rejects_missing_file(self) -> None:
        with self.assertRaises(ToolError) as context:
            load_arazzo_document(str(FIXTURES / "does-not-exist.yaml"))

        self.assertEqual(context.exception.code, "ARAZZO_FILE_NOT_FOUND")
