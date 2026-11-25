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

from tools.openapi_arazzo_tool.arazzo.criteria import (
    evaluate_criteria,
    evaluate_criterion,
)
from tools.openapi_arazzo_tool.arazzo.expression_evaluator import (
    HttpMessage,
    RuntimeContext,
)
from tools.openapi_arazzo_tool.errors import ExitCode, ToolError


class ArazzoCriterionEvaluatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.context = RuntimeContext(
            status_code=200,
            inputs={"minimum": "2", "enabled": True, "expected": "READY"},
            response=HttpMessage(body={"count": 3, "state": "ready"}),
        )

    def test_evaluates_comparisons_logical_operators_and_parentheses(self) -> None:
        criterion = {
            "condition": (
                "$statusCode == 200 && "
                "($response.body#/count >= $inputs.minimum || false)"
            )
        }

        self.assertTrue(evaluate_criterion(criterion, self.context))

    def test_compares_strings_case_insensitively_and_coerces_numbers(self) -> None:
        self.assertTrue(
            evaluate_criterion(
                {"condition": "$response.body#/state == $inputs.expected"},
                self.context,
            )
        )
        self.assertTrue(
            evaluate_criterion(
                {"condition": "$response.body#/count > '2'"},
                self.context,
            )
        )

    def test_handles_boolean_null_and_escaped_string_literals(self) -> None:
        self.assertTrue(
            evaluate_criterion({"condition": "$inputs.enabled"}, self.context)
        )
        self.assertTrue(evaluate_criterion({"condition": "null == null"}, self.context))
        self.assertTrue(
            evaluate_criterion({"condition": "'it''s' == 'IT''S'"}, self.context)
        )
        self.assertFalse(
            evaluate_criterion({"condition": "null != null"}, self.context)
        )

    def test_requires_all_criteria_to_pass(self) -> None:
        self.assertTrue(
            evaluate_criteria(
                [
                    {"condition": "$statusCode == 200"},
                    {"condition": "$response.body#/count == 3"},
                ],
                self.context,
            )
        )
        self.assertFalse(
            evaluate_criteria(
                [
                    {"condition": "$statusCode == 200"},
                    {"condition": "$response.body#/count == 4"},
                ],
                self.context,
            )
        )

    def test_rejects_unsupported_types_and_invalid_syntax(self) -> None:
        with self.assertRaises(ToolError) as unsupported:
            evaluate_criterion(
                {
                    "type": "jsonpath",
                    "context": "$response.body",
                    "condition": "$.count",
                },
                self.context,
            )
        with self.assertRaises(ToolError) as invalid:
            evaluate_criterion({"condition": "$statusCode === 200"}, self.context)

        self.assertEqual(
            unsupported.exception.code, "ARAZZO_CRITERION_EVALUATION_FAILED"
        )
        self.assertEqual(unsupported.exception.exit_code, ExitCode.TEST_ERROR)
        self.assertEqual(invalid.exception.code, "ARAZZO_CRITERION_EVALUATION_FAILED")
