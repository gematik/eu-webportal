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
from tools.openapi_arazzo_tool.arazzo.runtime_expressions import (
    find_runtime_expression_issues,
    parse_runtime_expressions,
)

FIXTURES = Path(__file__).parent / "fixtures" / "arazzo"


class ArazzoRuntimeExpressionValidationTest(unittest.TestCase):
    def test_parses_complete_and_embedded_expressions(self) -> None:
        expressions = parse_runtime_expressions(
            "id={$steps.create.outputs.widget.id#/value}&status={$statusCode}"
        )

        self.assertEqual(
            [expression.value for expression in expressions],
            ["$steps.create.outputs.widget.id#/value", "$statusCode"],
        )
        self.assertTrue(all(expression.embedded for expression in expressions))

    def test_accepts_supported_runtime_expression_syntax(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "valid" / "valid-runtime-expressions.yaml")
        )

        self.assertEqual(find_runtime_expression_issues(document), [])

    def test_rejects_invalid_and_forbidden_runtime_expression_syntax(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "invalid-runtime-expressions.yaml")
        )

        issues = find_runtime_expression_issues(document)

        self.assertEqual(len(issues), 6)
        self.assertTrue(
            all(issue.code == "ARAZZO_EXPRESSION_INVALID" for issue in issues)
        )
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("$environment.SECRET", messages)
        self.assertIn("missing closing '}'", messages)
        self.assertIn("$response.body#/item~2id", messages)
