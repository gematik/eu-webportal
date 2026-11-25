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
from tools.openapi_arazzo_tool.openapi.schemas import find_schema_issues

FIXTURES = Path(__file__).parent / "fixtures" / "openapi"


class OpenApiSchemaValidationTest(unittest.TestCase):
    def test_accepts_default_and_schema_local_dialects(self) -> None:
        document = load_openapi_document(
            str(FIXTURES / "valid" / "schema-dialect-override.yaml")
        )

        self.assertEqual(find_schema_issues(document), [])

    def test_rejects_non_absolute_root_dialect(self) -> None:
        document = load_openapi_document(
            str(FIXTURES / "invalid" / "invalid-json-schema-dialect.yaml")
        )

        issues = find_schema_issues(document)

        self.assertEqual(issues[0].code, "OPENAPI_JSON_SCHEMA_DIALECT_INVALID")
        self.assertIn("$.jsonSchemaDialect", issues[0].message)

    def test_rejects_unsupported_root_dialect_without_remote_lookup(self) -> None:
        document = load_openapi_document(
            str(FIXTURES / "invalid" / "unsupported-json-schema-dialect.yaml")
        )

        issues = find_schema_issues(document)

        self.assertEqual(issues[0].code, "OPENAPI_JSON_SCHEMA_DIALECT_UNSUPPORTED")

    def test_rejects_non_absolute_schema_override(self) -> None:
        document = load_openapi_document(
            str(FIXTURES / "invalid" / "invalid-schema-override.yaml")
        )

        issues = find_schema_issues(document)

        self.assertEqual(issues[0].code, "OPENAPI_JSON_SCHEMA_DIALECT_INVALID")
        self.assertIn("$.components.schemas.Widget.$schema", issues[0].message)

    def test_rejects_schema_invalid_for_effective_dialect(self) -> None:
        document = load_openapi_document(
            str(FIXTURES / "invalid" / "invalid-json-schema.yaml")
        )

        issues = find_schema_issues(document)

        self.assertEqual(issues[0].code, "OPENAPI_SCHEMA_INVALID")
        self.assertIn("$.components.schemas.Widget", issues[0].message)
