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

from tools.openapi_arazzo_tool.errors import ExitCode, ToolError
from tools.openapi_arazzo_tool.http.requests import build_http_request


class HttpRequestConstructionTest(unittest.TestCase):
    def test_builds_request_from_parameters_body_and_base_path(self) -> None:
        request = build_http_request(
            "post",
            "https://api.example.test/base/",
            "/widgets/{id}",
            [
                {"name": "id", "in": "path", "required": True},
                {"name": "tag", "in": "query"},
                {"name": "X-Trace", "in": "header"},
                {"name": "session", "in": "cookie"},
            ],
            {
                ("id", "path"): "a/b",
                ("tag", "query"): ["red", "blue"],
                ("X-Trace", "header"): "trace-1",
                ("session", "cookie"): "abc",
            },
            headers={"Accept": "application/json"},
            body_payload={"name": "Widget"},
            body_content_type="application/json",
        )

        self.assertEqual(request.method, "POST")
        self.assertEqual(
            request.url,
            "https://api.example.test/base/widgets/a%2Fb?tag=red&tag=blue",
        )
        self.assertEqual(
            request.headers,
            {
                "Accept": "application/json",
                "X-Trace": "trace-1",
                "Cookie": "session=abc",
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(request.body, b'{"name":"Widget"}')

    def test_builds_bodyless_request(self) -> None:
        request = build_http_request(
            "GET",
            "http://localhost:8080",
            "/health",
            [],
            {},
        )

        self.assertEqual(request.url, "http://localhost:8080/health")
        self.assertIsNone(request.body)

    def test_rejects_invalid_base_method_header_and_body_configuration(self) -> None:
        cases = (
            lambda: build_http_request("CONNECT", "https://example.test", "/", [], {}),
            lambda: build_http_request("GET", "/relative", "/", [], {}),
            lambda: build_http_request(
                "GET",
                "https://example.test",
                "/",
                [],
                {},
                headers={"X-Test": "value\r\nInjected: true"},
            ),
            lambda: build_http_request(
                "POST",
                "https://example.test",
                "/",
                [],
                {},
                body_payload={"name": "Widget"},
            ),
        )

        for build in cases:
            with self.subTest(build=build), self.assertRaises(ToolError) as context:
                build()
            self.assertEqual(context.exception.code, "HTTP_REQUEST_CONSTRUCTION_FAILED")
            self.assertEqual(context.exception.exit_code, ExitCode.TEST_ERROR)

    def test_rejects_case_insensitive_header_conflicts(self) -> None:
        with self.assertRaises(ToolError) as parameter_conflict:
            build_http_request(
                "GET",
                "https://example.test",
                "/",
                [{"name": "X-Trace", "in": "header"}],
                {("X-Trace", "header"): "from-parameter"},
                headers={"x-trace": "explicit"},
            )
        with self.assertRaises(ToolError) as content_type_conflict:
            build_http_request(
                "POST",
                "https://example.test",
                "/",
                [],
                {},
                headers={"content-type": "text/plain"},
                body_payload={},
                body_content_type="application/json",
            )

        self.assertIn("more than once", parameter_conflict.exception.message)
        self.assertIn("Content-Type", content_type_conflict.exception.message)

    def test_rejects_invalid_parameter_header_and_cookie_names(self) -> None:
        for location in ("header", "cookie"):
            with (
                self.subTest(location=location),
                self.assertRaises(ToolError) as context,
            ):
                build_http_request(
                    "GET",
                    "https://example.test",
                    "/",
                    [{"name": "bad\r\nInjected", "in": location}],
                    {("bad\r\nInjected", location): "value"},
                )

            self.assertEqual(context.exception.code, "HTTP_REQUEST_CONSTRUCTION_FAILED")
