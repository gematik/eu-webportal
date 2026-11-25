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

"""CLI integration coverage for immutable, independently versioned packages."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from tools.openapi_arazzo_tool.cli import run
from tools.openapi_arazzo_tool.errors import ExitCode, ToolError
from tools.openapi_arazzo_tool.mocking.package import load_mock_package

FIXTURES = Path(__file__).parent / "fixtures" / "cross"


class MockPackageCliTest(unittest.TestCase):
    def write_config(self, root: Path) -> Path:
        config = root / "tool.yaml"
        config.write_text(
            yaml.safe_dump(
                {
                    "openapi": [
                        str(FIXTURES / "invalid" / "unsupported-security-openapi.yaml")
                    ],
                    "arazzo": [
                        str(FIXTURES / "invalid" / "unsupported-security-workflow.yaml")
                    ],
                    "security": {"allowedRefRoots": [str(FIXTURES)]},
                    "mock": {"packageVersion": "1.2.3"},
                }
            ),
            encoding="utf-8",
        )
        return config

    def test_exports_mtls_specification_with_independent_generator_version(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.write_config(root)
            output = root / "mock"
            with (
                patch(
                    "tools.openapi_arazzo_tool.cli.generator_version",
                    return_value="0.4.0",
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                result = run(
                    [
                        "generate-mocks",
                        "--config",
                        str(config),
                        "--output",
                        str(output),
                    ]
                )

            manifest, routes = load_mock_package(output)
            self.assertEqual(result, ExitCode.SUCCESS)
            self.assertEqual(manifest["packageVersion"], "1.2.3")
            self.assertEqual(manifest["generatorVersion"], "0.4.0")
            self.assertEqual(len(routes), 2)
            self.assertEqual(routes[0].document["security"], [{"mTLS": []}])
            self.assertEqual(len(manifest["sources"]["arazzo"]), 1)

    def test_export_refuses_existing_release_without_modifying_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.write_config(root)
            output = root / "mock"
            arguments = [
                "generate-mocks",
                "--config",
                str(config),
                "--output",
                str(output),
            ]
            with (
                patch(
                    "tools.openapi_arazzo_tool.cli.generator_version",
                    return_value="0.4.0",
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                run(arguments)
                before = {
                    file.relative_to(output): file.read_bytes()
                    for file in output.rglob("*")
                    if file.is_file()
                }
                with self.assertRaises(ToolError):
                    run(arguments)

            after = {
                file.relative_to(output): file.read_bytes()
                for file in output.rglob("*")
                if file.is_file()
            }
            self.assertEqual(before, after)
