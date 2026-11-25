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

from tools.openapi_arazzo_tool.arazzo.expression_evaluator import (
    HttpMessage,
    Message,
    RuntimeContext,
    evaluate_expression_string,
)
from tools.openapi_arazzo_tool.errors import ExitCode, ToolError


class ArazzoExpressionEvaluatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.context = RuntimeContext(
            url="https://api.example.test/widgets/42",
            method="GET",
            status_code=200,
            self_uri="file:///workflows/widgets.yaml",
            inputs={"widget": {"id": "42"}, "active": True},
            outputs={"summary": {"count": 1}},
            steps={"create": {"outputs": {"widget": {"id": "42"}}}},
            workflows={"shared": {"inputs": {"locale": "de"}, "outputs": {"id": "42"}}},
            request=HttpMessage(
                headers={"X-Trace-ID": "trace-1"},
                query={"expand": "details"},
                path={"id": "42"},
                body={"name": "Widget"},
            ),
            response=HttpMessage(
                headers={"Location": "/widgets/42"},
                body={"items": [{"id": "42"}]},
            ),
            message=Message(headers={"X-Event": "created"}, payload={"id": "42"}),
            source_descriptions={
                "widgets": {
                    "url": "./widgets.yaml",
                    "type": "openapi",
                    "operations": {"widgets.read": {"operationId": "widgets.read"}},
                }
            },
            components={"parameters": {"locale": {"name": "locale", "in": "query"}}},
        )

    def test_preserves_native_types_for_complete_expressions(self) -> None:
        self.assertEqual(
            evaluate_expression_string("$inputs.widget#/id", self.context), "42"
        )
        self.assertEqual(
            evaluate_expression_string("$inputs.active", self.context), True
        )
        self.assertEqual(
            evaluate_expression_string("$response.body#/items/0", self.context),
            {"id": "42"},
        )
        self.assertEqual(evaluate_expression_string("$statusCode", self.context), 200)

    def test_resolves_request_response_step_workflow_and_message_values(self) -> None:
        self.assertEqual(
            evaluate_expression_string("$request.header.x-trace-id", self.context),
            "trace-1",
        )
        self.assertEqual(
            evaluate_expression_string("$request.query.expand", self.context), "details"
        )
        self.assertEqual(
            evaluate_expression_string("$request.path.id", self.context), "42"
        )
        self.assertEqual(
            evaluate_expression_string(
                "$steps.create.outputs.widget#/id", self.context
            ),
            "42",
        )
        self.assertEqual(
            evaluate_expression_string("$workflows.shared.outputs.id", self.context),
            "42",
        )
        self.assertEqual(
            evaluate_expression_string("$message.payload#/id", self.context), "42"
        )

    def test_resolves_source_descriptions_and_components(self) -> None:
        self.assertEqual(
            evaluate_expression_string("$sourceDescriptions.widgets.url", self.context),
            "./widgets.yaml",
        )
        self.assertEqual(
            evaluate_expression_string(
                "$sourceDescriptions.widgets.widgets.read", self.context
            ),
            {"operationId": "widgets.read"},
        )
        self.assertEqual(
            evaluate_expression_string("$components.parameters.locale", self.context),
            {"name": "locale", "in": "query"},
        )

    def test_interpolates_scalars_and_deterministic_json(self) -> None:
        value = evaluate_expression_string(
            "active={$inputs.active}&widget={$inputs.widget}&status={$statusCode}",
            self.context,
        )

        self.assertEqual(value, 'active=true&widget={"id":"42"}&status=200')

    def test_preserves_null_payloads(self) -> None:
        context = RuntimeContext(response=HttpMessage(body=None))

        self.assertIsNone(evaluate_expression_string("$response.body", context))
        self.assertEqual(
            evaluate_expression_string("body={$response.body}", context), "body=null"
        )

    def test_fails_explicitly_for_missing_values_and_pointer_targets(self) -> None:
        with self.assertRaises(ToolError) as missing:
            evaluate_expression_string("$inputs.missing", self.context)
        with self.assertRaises(ToolError) as pointer:
            evaluate_expression_string("$response.body#/items/4/id", self.context)

        self.assertEqual(missing.exception.code, "ARAZZO_EXPRESSION_EVALUATION_FAILED")
        self.assertEqual(missing.exception.exit_code, ExitCode.TEST_ERROR)
        self.assertIn("cannot be resolved", pointer.exception.message)
