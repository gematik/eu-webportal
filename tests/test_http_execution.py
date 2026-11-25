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

import httpx

from tools.openapi_arazzo_tool.errors import ToolError
from tools.openapi_arazzo_tool.http.execution import NetworkPolicy, execute_http_request
from tools.openapi_arazzo_tool.http.requests import HttpRequest


class HttpExecutionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = NetworkPolicy(
            frozenset({"api.example.test"}),
            frozenset({443}),
            max_response_bytes=16,
        )
        self.public_resolver = lambda host, port: ["8.8.8.8"]

    def test_executes_allowed_request_with_bounded_response(self) -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, content=b'{"ok":true}', request=request)
        )

        response = execute_http_request(
            HttpRequest("GET", "https://api.example.test/widgets"),
            self.policy,
            transport=transport,
            resolver=self.public_resolver,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, b'{"ok":true}')

    def test_revalidates_redirect_targets(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                302,
                headers={"Location": "http://169.254.169.254/latest"},
                request=request,
            )

        with self.assertRaises(ToolError) as context:
            execute_http_request(
                HttpRequest("GET", "https://api.example.test/widgets"),
                self.policy,
                transport=httpx.MockTransport(handler),
                resolver=self.public_resolver,
            )

        self.assertIn("not allowed", context.exception.message)

    def test_removes_credentials_from_cross_origin_redirect(self) -> None:
        seen_headers: list[httpx.Headers] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_headers.append(request.headers)
            if len(seen_headers) == 1:
                return httpx.Response(
                    302,
                    headers={"Location": "https://other.example.test/result"},
                    request=request,
                )
            return httpx.Response(200, request=request)

        policy = NetworkPolicy(
            frozenset({"api.example.test", "other.example.test"}),
            frozenset({443}),
        )
        execute_http_request(
            HttpRequest(
                "GET",
                "https://api.example.test/widgets",
                {"Authorization": "Bearer secret", "Cookie": "session=secret"},
            ),
            policy,
            transport=httpx.MockTransport(handler),
            resolver=self.public_resolver,
        )

        self.assertNotIn("Authorization", seen_headers[1])
        self.assertNotIn("Cookie", seen_headers[1])

    def test_blocks_private_resolved_addresses_and_disallowed_ports(self) -> None:
        for request, resolver in (
            (
                HttpRequest("GET", "https://api.example.test/widgets"),
                lambda host, port: ["127.0.0.1"],
            ),
            (
                HttpRequest("GET", "https://api.example.test:8443/widgets"),
                self.public_resolver,
            ),
        ):
            with self.subTest(request=request), self.assertRaises(ToolError):
                execute_http_request(
                    request,
                    self.policy,
                    transport=httpx.MockTransport(
                        lambda req: httpx.Response(200, request=req)
                    ),
                    resolver=resolver,
                )

    def test_allows_explicit_private_target_for_local_tests(self) -> None:
        policy = NetworkPolicy(
            frozenset({"localhost"}),
            frozenset({8080}),
            allow_private_addresses=True,
        )
        response = execute_http_request(
            HttpRequest("GET", "http://localhost:8080/health"),
            policy,
            transport=httpx.MockTransport(lambda req: httpx.Response(204, request=req)),
            resolver=lambda host, port: ["127.0.0.1"],
        )

        self.assertEqual(response.status_code, 204)

    def test_enforces_response_size_and_redirect_limits(self) -> None:
        with self.assertRaises(ToolError) as oversized:
            execute_http_request(
                HttpRequest("GET", "https://api.example.test/widgets"),
                self.policy,
                transport=httpx.MockTransport(
                    lambda req: httpx.Response(200, content=b"x" * 17, request=req)
                ),
                resolver=self.public_resolver,
            )
        with self.assertRaises(ToolError) as redirects:
            execute_http_request(
                HttpRequest("GET", "https://api.example.test/widgets"),
                NetworkPolicy(
                    frozenset({"api.example.test"}), frozenset({443}), redirect_limit=0
                ),
                transport=httpx.MockTransport(
                    lambda req: httpx.Response(
                        302, headers={"Location": "/next"}, request=req
                    )
                ),
                resolver=self.public_resolver,
            )

        self.assertIn("size limit", oversized.exception.message)
        self.assertIn("redirect limit", redirects.exception.message)
