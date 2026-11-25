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

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from tools.openapi_arazzo_tool.cli import run
from tools.openapi_arazzo_tool.errors import ExitCode, ToolError


class CliTest(unittest.TestCase):
    def test_help_is_available_without_configuration(self) -> None:
        with patch("sys.stdout") as stdout:
            self.assertEqual(run([]), ExitCode.SUCCESS)
            stdout.write.assert_called()

    def test_known_command_fails_explicitly(self) -> None:
        with self.assertRaises(ToolError) as context:
            run(["explain"])
        self.assertEqual(context.exception.code, "COMMAND_NOT_IMPLEMENTED")

    def test_missing_configuration_returns_configuration_error(self) -> None:
        with self.assertRaises(ToolError) as context:
            run(["validate-all", "--config", "missing-tool.yaml"])
        self.assertEqual(context.exception.exit_code, ExitCode.CONFIGURATION_ERROR)

    def test_scalar_configuration_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "tool.yaml"
            config.write_text("invalid", encoding="utf-8")
            with self.assertRaises(ToolError) as context:
                run(["report", "--config", str(config)])
        self.assertEqual(context.exception.code, "CONFIG_INVALID")

    def test_run_workflow_requires_identifier(self) -> None:
        with self.assertRaises(ToolError) as context:
            run(["run-workflow"])
        self.assertEqual(context.exception.code, "CONFIG_INVALID")

    def test_stop_mocks_describes_foreground_lifecycle(self) -> None:
        with patch("sys.stdout") as stdout:
            self.assertEqual(run(["stop-mocks"]), ExitCode.SUCCESS)
        stdout.write.assert_called()

    def test_package_start_uses_safe_defaults_and_keeps_validation_enabled(
        self,
    ) -> None:
        server = Mock(server_port=8080)
        with (
            patch(
                "tools.openapi_arazzo_tool.cli.load_mock_package",
                return_value=({"packageVersion": "1.0.0"}, ()),
            ),
            patch(
                "tools.openapi_arazzo_tool.cli.create_mock_server", return_value=server
            ) as create,
            patch("sys.stdout"),
        ):
            self.assertEqual(
                run(["start-mocks", "--package-dir", "mock-package"]),
                ExitCode.SUCCESS,
            )

        create.assert_called_once_with(
            "127.0.0.1",
            8080,
            (),
            validate_requests=True,
        )
        server.serve_forever.assert_called_once()
        server.server_close.assert_called_once()

    def test_package_start_accepts_explicit_network_overrides(self) -> None:
        server = Mock(server_port=9090)
        with (
            patch(
                "tools.openapi_arazzo_tool.cli.load_mock_package",
                return_value=({"packageVersion": "1.0.0"}, ()),
            ),
            patch(
                "tools.openapi_arazzo_tool.cli.create_mock_server", return_value=server
            ) as create,
            patch("sys.stdout"),
        ):
            self.assertEqual(
                run(
                    [
                        "start-mocks",
                        "--package-dir",
                        "mock-package",
                        "--bind-host",
                        "0.0.0.0",
                        "--port",
                        "9090",
                    ]
                ),
                ExitCode.SUCCESS,
            )

        create.assert_called_once_with(
            "0.0.0.0",
            9090,
            (),
            validate_requests=True,
        )

    def test_package_start_rejects_invalid_port_before_binding(self) -> None:
        with (
            patch(
                "tools.openapi_arazzo_tool.cli.load_mock_package",
                return_value=({"packageVersion": "1.0.0"}, ()),
            ),
            patch("tools.openapi_arazzo_tool.cli.create_mock_server") as create,
        ):
            with self.assertRaises(ToolError) as context:
                run(
                    [
                        "start-mocks",
                        "--package-dir",
                        "mock-package",
                        "--port",
                        "70000",
                    ]
                )

        self.assertEqual(context.exception.code, "CONFIG_INVALID")
        create.assert_not_called()
