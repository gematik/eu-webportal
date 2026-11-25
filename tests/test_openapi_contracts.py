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
from typing import Any

import httpx

from tools.openapi_arazzo_tool.errors import ToolError
from tools.openapi_arazzo_tool.http.execution import HttpResponse
from tools.openapi_arazzo_tool.http.requests import HttpRequest
from tools.openapi_arazzo_tool.openapi.contracts import (
    select_response_definition,
    validate_request_contract,
    validate_response_contract,
)


class OpenApiContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.document: dict[str, Any] = {
            "openapi": "3.1.0",
            "components": {
                "parameters": {
                    "Page": {
                        "name": "page",
                        "in": "query",
                        "required": True,
                        "schema": {"type": "integer", "minimum": 1},
                    }
                },
                "schemas": {
                    "Widget": {
                        "type": "object",
                        "required": ["id"],
                        "properties": {"id": {"type": "string"}},
                    }
                },
            },
        }
        self.operation: dict[str, Any] = {
            "parameters": [{"$ref": "#/components/parameters/Page"}],
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "required": ["name"],
                            "properties": {"name": {"type": "string"}},
                        }
                    }
                },
            },
            "responses": {
                "201": {
                    "description": "Created",
                    "headers": {
                        "Location": {
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    },
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Widget"}
                        }
                    },
                },
                "2XX": {"description": "Other success"},
                "default": {"description": "Other"},
            },
        }

    def test_validates_request_values_and_body(self) -> None:
        request = HttpRequest(
            "POST",
            "https://example.test/widgets?page=1",
            {"Content-Type": "application/json"},
            b'{"name":"Widget"}',
        )
        validate_request_contract(
            self.document,
            {},
            self.operation,
            {("page", "query"): 1},
            request,
            {"name": "Widget"},
            "application/json",
        )

        with self.assertRaises(ToolError):
            validate_request_contract(
                self.document,
                {},
                self.operation,
                {("page", "query"): 0},
                request,
                {},
                "application/json",
            )

    def test_validates_response_headers_content_and_schema(self) -> None:
        payload = validate_response_contract(
            self.document,
            self.operation,
            HttpResponse(
                201,
                httpx.Headers(
                    {
                        "Location": "/widgets/1",
                        "Content-Type": "application/json; charset=utf-8",
                    }
                ),
                b'{"id":"widget-1"}',
                "https://example.test/widgets",
            ),
        )
        self.assertEqual(payload, {"id": "widget-1"})

        with self.assertRaises(ToolError) as context:
            validate_response_contract(
                self.document,
                self.operation,
                HttpResponse(
                    201,
                    httpx.Headers({"Content-Type": "application/json"}),
                    b'{"name":"missing-id"}',
                    "https://example.test/widgets",
                ),
            )
        self.assertIn("Location", context.exception.message)

    def test_selects_most_specific_response(self) -> None:
        responses = self.operation["responses"]
        self.assertIs(select_response_definition(responses, 201), responses["201"])
        self.assertIs(select_response_definition(responses, 202), responses["2XX"])
        self.assertIs(select_response_definition(responses, 404), responses["default"])

    def test_rejects_response_violating_referenced_schema(self) -> None:
        with self.assertRaisesRegex(ToolError, "violates its schema"):
            validate_response_contract(
                self.document,
                self.operation,
                HttpResponse(
                    201,
                    httpx.Headers(
                        {"Location": "/widgets/1", "Content-Type": "application/json"}
                    ),
                    b'{"name":"missing-id"}',
                    "https://example.test/widgets",
                ),
            )
