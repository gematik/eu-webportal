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

import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx

from tools.openapi_arazzo_tool.arazzo.model import ArazzoDocument
from tools.openapi_arazzo_tool.arazzo.runner import list_workflows, run_workflow
from tools.openapi_arazzo_tool.cross_validation.sources import ResolvedSources
from tools.openapi_arazzo_tool.errors import ToolError
from tools.openapi_arazzo_tool.http.execution import HttpResponse, NetworkPolicy
from tools.openapi_arazzo_tool.http.requests import HttpRequest


class ArazzoRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.openapi: dict[str, Any] = {
            "openapi": "3.1.0",
            "servers": [{"url": "https://api.example.test"}],
            "paths": {
                "/widgets": {
                    "post": {
                        "operationId": "widgets.create",
                        "parameters": [
                            {
                                "name": "locale",
                                "in": "query",
                                "required": True,
                                "schema": {"type": "string"},
                            }
                        ],
                        "requestBody": {
                            "content": {
                                "application/json": {"schema": {"type": "object"}}
                            }
                        },
                        "responses": {
                            "201": {
                                "description": "Created",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "required": ["id"],
                                            "properties": {"id": {"type": "string"}},
                                        }
                                    }
                                },
                            },
                            "500": {
                                "description": "Temporary failure",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "required": ["id"],
                                            "properties": {"id": {"type": "string"}},
                                        }
                                    }
                                },
                            },
                        },
                    }
                },
                "/widgets/{id}": {
                    "get": {
                        "operationId": "widgets.read",
                        "parameters": [
                            {
                                "name": "id",
                                "in": "path",
                                "required": True,
                                "schema": {"type": "string"},
                            }
                        ],
                        "responses": {"200": {"description": "Found"}},
                    }
                },
            },
        }
        self.document = ArazzoDocument(
            "workflow.yaml",
            "1.1.0",
            {
                "arazzo": "1.1.0",
                "workflows": [
                    {
                        "workflowId": "create-and-read",
                        "inputs": {
                            "type": "object",
                            "required": ["locale"],
                            "properties": {"locale": {"type": "string"}},
                        },
                        "steps": [
                            {
                                "stepId": "create",
                                "operationId": "api.widgets.create",
                                "parameters": [
                                    {
                                        "name": "locale",
                                        "in": "query",
                                        "value": "$inputs.locale",
                                    }
                                ],
                                "requestBody": {
                                    "contentType": "application/json",
                                    "payload": {"locale": "$inputs.locale"},
                                },
                                "successCriteria": [
                                    {"condition": "$statusCode == 201"}
                                ],
                                "outputs": {"id": "$response.body#/id"},
                            },
                            {
                                "stepId": "read",
                                "operationId": "api.widgets.read",
                                "parameters": [
                                    {
                                        "name": "id",
                                        "in": "path",
                                        "value": "$steps.create.outputs.id",
                                    }
                                ],
                                "outputs": {"url": "$url"},
                            },
                        ],
                        "outputs": {"id": "$steps.create.outputs.id"},
                    }
                ],
            },
        )
        self.sources = ResolvedSources(
            {"api": SimpleNamespace(raw=self.openapi, path="api.yaml")},
            [],
        )
        self.policy = NetworkPolicy(frozenset({"api.example.test"}), frozenset({443}))

    def test_lists_and_executes_sequential_workflow(self) -> None:
        requests: list[HttpRequest] = []

        def executor(request: HttpRequest, policy: NetworkPolicy) -> HttpResponse:
            requests.append(request)
            if request.method == "POST":
                return HttpResponse(
                    201,
                    httpx.Headers({"Content-Type": "application/json"}),
                    b'{"id":"widget-1"}',
                    request.url,
                )
            return HttpResponse(200, httpx.Headers(), b"", request.url)

        result = run_workflow(
            self.document,
            self.sources,
            "create-and-read",
            {"locale": "de-DE"},
            self.policy,
            executor=executor,
        )

        self.assertEqual(list_workflows(self.document), ("create-and-read",))
        self.assertTrue(result.success)
        self.assertEqual(result.outputs, {"id": "widget-1"})
        self.assertEqual(
            requests[0].url, "https://api.example.test/widgets?locale=de-DE"
        )
        self.assertEqual(requests[0].body, b'{"locale":"de-DE"}')
        self.assertEqual(requests[1].url, "https://api.example.test/widgets/widget-1")

    def test_retries_then_succeeds(self) -> None:
        step = self.document.raw["workflows"][0]["steps"][0]
        step["onFailure"] = [
            {
                "name": "retry",
                "type": "retry",
                "retryLimit": 1,
            }
        ]
        calls = 0

        def executor(request: HttpRequest, policy: NetworkPolicy) -> HttpResponse:
            nonlocal calls
            calls += 1
            if request.method == "GET":
                return HttpResponse(200, httpx.Headers(), b"", request.url)
            status = 500 if calls == 1 else 201
            return HttpResponse(
                status,
                httpx.Headers({"Content-Type": "application/json"}),
                b'{"id":"widget-1"}',
                request.url,
            )

        result = run_workflow(
            self.document,
            self.sources,
            "create-and-read",
            {"locale": "de-DE"},
            self.policy,
            executor=executor,
        )

        self.assertTrue(result.success)
        self.assertEqual(calls, 3)

    def test_rejects_invalid_inputs_and_timeout(self) -> None:
        with self.assertRaises(ToolError) as inputs:
            run_workflow(
                self.document,
                self.sources,
                "create-and-read",
                {},
                self.policy,
            )
        times = iter((0.0, 1.0))
        with self.assertRaises(ToolError) as timeout:
            run_workflow(
                self.document,
                self.sources,
                "create-and-read",
                {"locale": "de-DE"},
                self.policy,
                workflow_timeout_seconds=0.5,
                clock=lambda: next(times),
            )

        self.assertIn("required", inputs.exception.message)
        self.assertIn("timed out", timeout.exception.message)

    def test_rejects_non_mapping_workflow_actions(self) -> None:
        self.document.raw["workflows"][0]["steps"][0]["onSuccess"] = [None]

        def executor(request: HttpRequest, policy: NetworkPolicy) -> HttpResponse:
            return HttpResponse(
                201,
                httpx.Headers({"Content-Type": "application/json"}),
                b'{"id":"widget-1"}',
                request.url,
            )

        with self.assertRaisesRegex(ToolError, "Workflow action must be a mapping"):
            run_workflow(
                self.document,
                self.sources,
                "create-and-read",
                {"locale": "de-DE"},
                self.policy,
                executor=executor,
            )

    def test_caps_request_timeout_to_remaining_workflow_time(self) -> None:
        observed_timeout: float | None = None
        times = iter((0.0, 0.25, 0.25, 0.5, 0.5, 0.75))

        def executor(request: HttpRequest, policy: NetworkPolicy) -> HttpResponse:
            nonlocal observed_timeout
            observed_timeout = policy.request_timeout_seconds
            return HttpResponse(
                201,
                httpx.Headers({"Content-Type": "application/json"}),
                b'{"id":"widget-1"}',
                request.url,
            )

        document = ArazzoDocument(
            self.document.path,
            self.document.version,
            {
                **self.document.raw,
                "workflows": [
                    {
                        **self.document.raw["workflows"][0],
                        "steps": [self.document.raw["workflows"][0]["steps"][0]],
                    }
                ],
            },
        )
        run_workflow(
            document,
            self.sources,
            "create-and-read",
            {"locale": "de-DE"},
            self.policy,
            workflow_timeout_seconds=1.0,
            executor=executor,
            clock=lambda: next(times),
        )

        self.assertEqual(observed_timeout, 0.75)

    def test_injects_scoped_credential_without_exposing_echoed_secret(self) -> None:
        self.openapi["components"] = {
            "securitySchemes": {"token": {"type": "http", "scheme": "bearer"}}
        }
        self.openapi["paths"]["/widgets"]["post"]["security"] = [{"token": []}]
        self.document.raw["workflows"][0]["steps"] = [
            self.document.raw["workflows"][0]["steps"][0]
        ]
        binding = {
            "env": "TEST_RUNNER_TOKEN",
            "workflowIds": ["create-and-read"],
            "origins": ["https://api.example.test"],
            "methods": ["POST"],
            "paths": ["/widgets"],
        }

        def executor(request: HttpRequest, policy: NetworkPolicy) -> HttpResponse:
            self.assertEqual(request.headers["Authorization"], "Bearer hidden-token")
            self.assertEqual(policy.redirect_limit, 0)
            return HttpResponse(
                201,
                httpx.Headers({"Content-Type": "application/json"}),
                b'{"id":"hidden-token"}',
                request.url,
            )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trusted.yaml"
            path.write_text("trusted workflow", encoding="utf-8")
            binding["workflowSha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            document = ArazzoDocument(
                str(path), self.document.version, self.document.raw
            )
            previous = os.environ.get("TEST_RUNNER_TOKEN")
            os.environ["TEST_RUNNER_TOKEN"] = "hidden-token"
            try:
                result = run_workflow(
                    document,
                    self.sources,
                    "create-and-read",
                    {"locale": "de-DE"},
                    self.policy,
                    executor=executor,
                    auth={"schemes": {"token": binding}},
                    trusted=True,
                )
            finally:
                if previous is None:
                    os.environ.pop("TEST_RUNNER_TOKEN", None)
                else:
                    os.environ["TEST_RUNNER_TOKEN"] = previous
        self.assertEqual(result.outputs["id"], "[REDACTED]")
        self.assertEqual(result.steps[0].outputs["id"], "[REDACTED]")
