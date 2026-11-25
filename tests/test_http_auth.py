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

import os
import unittest
from collections.abc import Iterator
from contextlib import contextmanager

from tools.openapi_arazzo_tool.errors import ToolError
from tools.openapi_arazzo_tool.http.auth import authorize_request, redact
from tools.openapi_arazzo_tool.http.requests import HttpRequest


@contextmanager
def _secret(value: str) -> Iterator[None]:
    previous = os.environ.get("TEST_AUTH_SECRET")
    os.environ["TEST_AUTH_SECRET"] = value
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("TEST_AUTH_SECRET", None)
        else:
            os.environ["TEST_AUTH_SECRET"] = previous


class HttpAuthTest(unittest.TestCase):
    def setUp(self) -> None:
        self.document = {
            "components": {
                "securitySchemes": {
                    "token": {"type": "http", "scheme": "bearer"},
                    "key": {"type": "apiKey", "in": "query", "name": "api_key"},
                    "password": {"type": "http", "scheme": "basic"},
                }
            },
            "security": [{"token": [], "key": []}, {"password": []}],
        }
        self.binding = {
            "env": "TEST_AUTH_SECRET",
            "workflowIds": ["safe-workflow"],
            "origins": ["https://api.example.test"],
            "methods": ["GET"],
            "paths": ["/widgets/{id}"],
            "workflowSha256": "a" * 64,
        }
        self.request = HttpRequest("GET", "https://api.example.test/widgets/42")

    def test_injects_all_and_credentials_and_redacts_values(self) -> None:
        auth = {"schemes": {"token": self.binding, "key": self.binding}}
        with _secret("very-secret"):
            request, secrets = authorize_request(
                self.request,
                self.document,
                {},
                "safe-workflow",
                "/widgets/{id}",
                auth,
                trusted=True,
                workflow_sha256="a" * 64,
            )
        self.assertEqual(request.headers["Authorization"], "Bearer very-secret")
        self.assertIn("api_key=very-secret", request.url)
        self.assertEqual(
            redact({"value": request.url}, secrets)["value"].count("[REDACTED]"), 1
        )

    def test_uses_second_or_alternative_when_first_unconfigured(self) -> None:
        auth = {"schemes": {"password": {**self.binding, "username": "tester"}}}
        with _secret("very-secret"):
            request, secrets = authorize_request(
                self.request,
                self.document,
                {},
                "safe-workflow",
                "/widgets/{id}",
                auth,
                trusted=True,
                workflow_sha256="a" * 64,
            )
        self.assertTrue(request.headers["Authorization"].startswith("Basic "))
        self.assertNotIn(
            request.headers["Authorization"].split(" ", 1)[1],
            redact(request.headers["Authorization"], secrets),
        )

    def test_rejects_untrusted_wrong_origin_or_missing_credential(self) -> None:
        auth = {"schemes": {"token": self.binding, "key": self.binding}}
        with _secret("very-secret"):
            for trusted, workflow, path in (
                (False, "safe-workflow", "/widgets/{id}"),
                (True, "unsafe-workflow", "/widgets/{id}"),
                (True, "safe-workflow", "/other"),
            ):
                with self.subTest(trusted=trusted, workflow=workflow, path=path):
                    with self.assertRaises(ToolError):
                        authorize_request(
                            self.request,
                            self.document,
                            {},
                            workflow,
                            path,
                            auth,
                            trusted=trusted,
                            workflow_sha256="a" * 64,
                        )
        with _secret(""), self.assertRaises(ToolError) as error:
            authorize_request(
                self.request,
                self.document,
                {},
                "safe-workflow",
                "/widgets/{id}",
                auth,
                trusted=True,
                workflow_sha256="a" * 64,
            )
        self.assertIn("missing", error.exception.message)

    def test_rejects_modified_workflow_fingerprint(self) -> None:
        with _secret("very-secret"):
            with self.assertRaises(ToolError):
                authorize_request(
                    self.request,
                    self.document,
                    {},
                    "safe-workflow",
                    "/widgets/{id}",
                    {"schemes": {"token": self.binding, "key": self.binding}},
                    trusted=True,
                    workflow_sha256="b" * 64,
                )
