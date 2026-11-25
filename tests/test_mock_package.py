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
import json
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

from tools.openapi_arazzo_tool.errors import ExitCode, ToolError
from tools.openapi_arazzo_tool.mocking.model import MockResponse, generate_mock_routes
from tools.openapi_arazzo_tool.mocking.package import (
    load_mock_package,
    write_mock_package,
)
from tools.openapi_arazzo_tool.mocking.server import create_mock_server
from tools.openapi_arazzo_tool.openapi.model import OpenApiDocument


class MockPackageExportTest(unittest.TestCase):
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
                                                "default": {"value": {"id": "one"}}
                                            }
                                        }
                                    },
                                }
                            },
                        }
                    }
                },
            },
        )
        self.routes = generate_mock_routes([self.document])

    def create_package(self, root: Path, directory_name: str) -> Path:
        source = root / "api.yaml"
        source.write_text("openapi: 3.1.0\n", encoding="utf-8")
        return write_mock_package(
            root / directory_name,
            "1.2.3",
            "0.4.0",
            [self.document],
            self.routes,
            [source],
            [],
        )

    def test_writes_deterministic_package_and_verifiable_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "api.yaml"
            source.write_text("openapi: 3.1.0\n", encoding="utf-8")
            first = self.create_package(root, "first")
            second = self.create_package(root, "second")

            manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["packageVersion"], "1.2.3")
            self.assertEqual(manifest["generatorVersion"], "0.4.0")
            self.assertEqual(manifest["formatVersion"], "1.0.0")
            self.assertEqual(
                manifest["files"]["runtime/routes.json"],
                hashlib.sha256(
                    (first / "runtime/routes.json").read_bytes()
                ).hexdigest(),
            )
            self.assertEqual(
                (first / "runtime/routes.json").read_bytes(),
                (second / "runtime/routes.json").read_bytes(),
            )
            self.assertEqual(
                (first / "runtime/contracts/openapi-0001.json").read_bytes(),
                (second / "runtime/contracts/openapi-0001.json").read_bytes(),
            )
            self.assertEqual(
                (first / "sources/openapi/0001-api.yaml").read_bytes(),
                source.read_bytes(),
            )
            first_files = {
                file.relative_to(first).as_posix(): file.read_bytes()
                for file in first.rglob("*")
                if file.is_file()
            }
            second_files = {
                file.relative_to(second).as_posix(): file.read_bytes()
                for file in second.rglob("*")
                if file.is_file()
            }
            self.assertEqual(first_files, second_files)

    def test_failed_prepublication_check_does_not_publish_or_leave_staging_files(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            failure = ToolError("MOCK_PACKAGE_INVALID", "Incomplete package.")
            with patch(
                "tools.openapi_arazzo_tool.mocking.package.load_mock_package",
                side_effect=failure,
            ) as verify:
                with self.assertRaises(ToolError):
                    self.create_package(root, "mock")

            verify.assert_called_once()
            self.assertFalse((root / "mock").exists())
            self.assertEqual(list(root.iterdir()), [root / "api.yaml"])

    def test_export_rejects_response_status_outside_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "api.yaml"
            source.write_text("openapi: 3.1.0\n", encoding="utf-8")
            invalid = replace(
                self.routes[0],
                response=MockResponse(500, self.routes[0].response.headers, b"{}"),
            )
            with self.assertRaises(ToolError):
                write_mock_package(
                    root / "mock",
                    "1.0.0",
                    "0.4.0",
                    [self.document],
                    [invalid],
                    [source],
                    [],
                )

            self.assertFalse((root / "mock").exists())
            self.assertEqual(list(root.iterdir()), [source])

    def test_export_preserves_fractional_millisecond_delay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "api.yaml"
            source.write_text("openapi: 3.1.0\n", encoding="utf-8")
            delayed = replace(self.routes[0], delay_seconds=0.0015)
            package = write_mock_package(
                root / "mock",
                "1.0.0",
                "0.4.0",
                [self.document],
                [delayed],
                [source],
                [],
            )
            _, loaded = load_mock_package(package)

            self.assertEqual(loaded[0].delay_seconds, delayed.delay_seconds)

    def test_rejects_invalid_semver_and_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ToolError):
                write_mock_package(
                    root / "invalid",
                    "latest",
                    "0.4.0",
                    [self.document],
                    self.routes,
                    [],
                    [],
                )
            source = root / "api.yaml"
            source.write_text("openapi: 3.1.0\n", encoding="utf-8")
            existing = root / "existing"
            existing.mkdir()
            with self.assertRaises(ToolError):
                write_mock_package(
                    existing,
                    "1.0.0",
                    "0.4.0",
                    [self.document],
                    self.routes,
                    [source],
                    [],
                )

    def test_loads_generated_route_and_contract_without_source_parsing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = self.create_package(root, "mock")

            manifest, routes = load_mock_package(package)

            self.assertEqual(manifest["packageVersion"], "1.2.3")
            self.assertEqual(len(routes), 1)
            self.assertEqual(routes[0].operation_id, "getWidget")
            self.assertEqual(routes[0].path_template, "/widgets/{id}")
            self.assertEqual(json.loads(routes[0].response.body), {"id": "one"})
            self.assertEqual(routes[0].operation["operationId"], "getWidget")

    def test_rejects_modified_package_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = self.create_package(Path(directory), "mock")
            route_file = package / "runtime" / "routes.json"
            route_file.write_bytes(route_file.read_bytes() + b" ")

            with self.assertRaises(ToolError) as context:
                load_mock_package(package)

            self.assertEqual(context.exception.code, "MOCK_PACKAGE_INVALID")
            self.assertEqual(context.exception.exit_code, ExitCode.VALIDATION_ERROR)

    def test_rejects_unsupported_package_format(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = self.create_package(Path(directory), "mock")
            manifest_path = package / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["formatVersion"] = "2.0.0"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            with self.assertRaises(ToolError) as context:
                load_mock_package(package)

            self.assertEqual(context.exception.code, "MOCK_PACKAGE_INVALID")
            self.assertEqual(context.exception.exit_code, ExitCode.VALIDATION_ERROR)

    def test_persists_reference_provenance_and_rejects_unknown_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "api.yaml"
            source.write_text("openapi: 3.1.0\n", encoding="utf-8")
            references = [
                {
                    "source": {"kind": "openapi", "index": 1},
                    "target": {"kind": "openapi", "index": 1},
                    "reference": "#/components/schemas/Widget",
                    "location": "/components/schemas/Widget/$ref",
                }
            ]
            package = write_mock_package(
                root / "mock",
                "1.0.0",
                "0.4.0",
                [self.document],
                self.routes,
                [source],
                [],
                source_references=references,
            )
            manifest, _ = load_mock_package(package)
            self.assertEqual(manifest["sourceReferences"], references)
            manifest["sourceReferences"][0]["target"]["index"] = 2
            (package / "manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )

            with self.assertRaises(ToolError) as context:
                load_mock_package(package)
            self.assertEqual(context.exception.code, "MOCK_PACKAGE_INVALID")

    def test_package_runtime_keeps_request_contract_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            package = self.create_package(Path(directory), "mock")
            _, routes = load_mock_package(package)
            server = create_mock_server("127.0.0.1", 0, routes)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}/widgets/one"
                with self.assertRaises(HTTPError) as invalid:
                    urlopen(url, timeout=2)
                self.assertEqual(invalid.exception.code, 400)
                invalid.exception.close()
                with urlopen(f"{url}?verbose=true", timeout=2) as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(json.load(response), {"id": "one"})
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
