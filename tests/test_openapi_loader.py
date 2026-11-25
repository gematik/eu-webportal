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

from tools.openapi_arazzo_tool.errors import ExitCode, ToolError
from tools.openapi_arazzo_tool.openapi.loader import load_openapi_document

FIXTURES = Path(__file__).parent / "fixtures" / "openapi"


class OpenApiLoaderTest(unittest.TestCase):
    def test_loads_valid_openapi_31_document(self) -> None:
        document = load_openapi_document(str(FIXTURES / "valid" / "minimal-3.1.yaml"))
        self.assertEqual(document.version, "3.1.0")
        self.assertEqual(document.raw["info"]["title"], "Minimal Valid API")

    def test_rejects_openapi_30(self) -> None:
        with self.assertRaises(ToolError) as context:
            load_openapi_document(str(FIXTURES / "invalid" / "version-3.0.yaml"))
        self.assertEqual(context.exception.code, "OPENAPI_VERSION_UNSUPPORTED")
        self.assertEqual(context.exception.exit_code, ExitCode.VALIDATION_ERROR)

    def test_rejects_openapi_32(self) -> None:
        with self.assertRaises(ToolError) as context:
            load_openapi_document(str(FIXTURES / "invalid" / "version-3.2.yaml"))
        self.assertEqual(context.exception.code, "OPENAPI_VERSION_UNSUPPORTED")

    def test_rejects_broken_syntax(self) -> None:
        with self.assertRaises(ToolError) as context:
            load_openapi_document(str(FIXTURES / "invalid" / "broken-syntax.yaml"))
        self.assertEqual(context.exception.code, "OPENAPI_SYNTAX_INVALID")

    def test_rejects_non_mapping_root(self) -> None:
        with self.assertRaises(ToolError) as context:
            load_openapi_document(str(FIXTURES / "invalid" / "non-mapping-root.yaml"))
        self.assertEqual(context.exception.code, "OPENAPI_SYNTAX_INVALID")

    def test_rejects_missing_file(self) -> None:
        with self.assertRaises(ToolError) as context:
            load_openapi_document(str(FIXTURES / "does-not-exist.yaml"))
        self.assertEqual(context.exception.code, "OPENAPI_FILE_NOT_FOUND")
