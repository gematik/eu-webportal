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

import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from tools.openapi_arazzo_tool.errors import ToolError
from tools.openapi_arazzo_tool.mocking.model import generate_mock_routes, mock_manifest
from tools.openapi_arazzo_tool.mocking.server import create_mock_server
from tools.openapi_arazzo_tool.openapi.model import OpenApiDocument


class MockingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.document = OpenApiDocument(
            "api.yaml",
            "3.1.0",
            {
                "openapi": "3.1.0",
                "paths": {
                    "/widgets/{id}": {
                        "get": {
                            "operationId": "getWidget",
                            "parameters": [
                                {
                                    "name": "id",
                                    "in": "path",
                                    "required": True,
                                    "schema": {"type": "string"},
                                },
                                {
                                    "name": "verbose",
                                    "in": "query",
                                    "required": True,
                                    "schema": {"type": "boolean"},
                                },
                            ],
                            "responses": {
                                "200": {
                                    "description": "Found",
                                    "content": {
                                        "application/json": {
                                            "examples": {
                                                "first": {"value": {"id": "first"}},
                                                "second": {"value": {"id": "second"}},
                                            }
                                        }
                                    },
                                },
                                "404": {
                                    "description": "Missing",
                                    "content": {
                                        "application/json": {
                                            "schema": {
                                                "type": "object",
                                                "required": ["error"],
                                                "properties": {
                                                    "error": {
                                                        "type": "string",
                                                        "default": "missing",
                                                    }
                                                },
                                            }
                                        }
                                    },
                                },
                            },
                        }
                    }
                },
            },
        )

    def test_selects_first_example_and_explicit_scenario(self) -> None:
        default = generate_mock_routes([self.document])
        scenario = generate_mock_routes(
            [self.document],
            scenario={"getWidget": {"response": 404}},
            seed=42,
        )

        self.assertEqual(json.loads(default[0].response.body), {"id": "first"})
        self.assertEqual(scenario[0].response.status_code, 404)
        self.assertEqual(json.loads(scenario[0].response.body), {"error": "missing"})
        self.assertEqual(mock_manifest(scenario)[0]["operationId"], "getWidget")

    def test_named_example_has_priority(self) -> None:
        routes = generate_mock_routes(
            [self.document],
            example_names={"getWidget": "second"},
        )
        self.assertEqual(json.loads(routes[0].response.body), {"id": "second"})

    def test_rejects_injected_scenario_headers(self) -> None:
        with self.assertRaises(ToolError):
            generate_mock_routes(
                [self.document],
                scenario={
                    "getWidget": {
                        "response": 200,
                        "headers": {"X-Test": "safe\r\nInjected: true"},
                    }
                },
            )

    def test_server_validates_requests_before_mocking(self) -> None:
        routes = generate_mock_routes([self.document])
        server = create_mock_server("127.0.0.1", 0, routes)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(
                Request(
                    f"http://127.0.0.1:{server.server_port}/widgets/widget-1?verbose=true"
                ),
                timeout=2,
            ) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(json.load(response), {"id": "first"})
            with self.assertRaises(HTTPError) as missing:
                urlopen(
                    Request(f"http://127.0.0.1:{server.server_port}/unknown"),
                    timeout=2,
                )
            self.assertEqual(missing.exception.code, 404)
            missing.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_invalid_request_cannot_receive_success_mock(self) -> None:
        routes = generate_mock_routes([self.document])
        server = create_mock_server("127.0.0.1", 0, routes)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with self.assertRaises(HTTPError) as invalid:
                urlopen(
                    Request(f"http://127.0.0.1:{server.server_port}/widgets/widget-1"),
                    timeout=2,
                )
            self.assertEqual(invalid.exception.code, 400)
            invalid.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
