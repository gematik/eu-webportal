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

from tools.openapi_arazzo_tool.cli import run
from tools.openapi_arazzo_tool.errors import ExitCode, ToolError

FIXTURES = Path(__file__).parent / "fixtures" / "arazzo"
CROSS_FIXTURES = Path(__file__).parent / "fixtures" / "cross"


class ValidateArazzoCliTest(unittest.TestCase):
    def _write_config(self, directory: Path, *arazzo_paths: Path) -> Path:
        config = directory / "tool.yaml"
        entries = "\n".join(f"  - {path}" for path in arazzo_paths)
        config.write_text(f"arazzo:\n{entries}\n", encoding="utf-8")
        return config

    def test_succeeds_for_valid_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory), FIXTURES / "valid" / "minimal-1.1.yaml"
            )

            self.assertEqual(
                run(["validate-arazzo", "--config", str(config)]), ExitCode.SUCCESS
            )

    def test_fails_for_unsupported_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory), FIXTURES / "invalid" / "version-1.0.yaml"
            )

            with self.assertRaises(ToolError) as context:
                run(["validate-arazzo", "--config", str(config)])

        self.assertEqual(context.exception.code, "ARAZZO_VALIDATION_FAILED")
        self.assertEqual(context.exception.exit_code, ExitCode.VALIDATION_ERROR)

    def test_fails_when_no_documents_configured(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "tool.yaml"
            config.write_text("arazzo: []\n", encoding="utf-8")

            with self.assertRaises(ToolError) as context:
                run(["validate-arazzo", "--config", str(config)])

        self.assertEqual(context.exception.code, "CONFIG_INVALID")
        self.assertEqual(context.exception.exit_code, ExitCode.CONFIGURATION_ERROR)

    def test_fails_for_invalid_document_structure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory),
                FIXTURES / "invalid" / "invalid-document-structure.yaml",
            )

            with self.assertRaises(ToolError) as context:
                run(["validate-arazzo", "--config", str(config)])

        self.assertEqual(context.exception.code, "ARAZZO_VALIDATION_FAILED")

    def test_fails_for_invalid_workflows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory),
                FIXTURES / "invalid" / "invalid-workflows.yaml",
            )

            with self.assertRaises(ToolError) as context:
                run(["validate-arazzo", "--config", str(config)])

        self.assertEqual(context.exception.code, "ARAZZO_VALIDATION_FAILED")

    def test_fails_for_invalid_step_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory),
                FIXTURES / "invalid" / "invalid-step-inputs.yaml",
            )

            with self.assertRaises(ToolError) as context:
                run(["validate-arazzo", "--config", str(config)])

        self.assertEqual(context.exception.code, "ARAZZO_VALIDATION_FAILED")

    def test_fails_for_invalid_outputs_and_success_criteria(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory),
                FIXTURES / "invalid" / "invalid-outputs-and-criteria.yaml",
            )

            with self.assertRaises(ToolError) as context:
                run(["validate-arazzo", "--config", str(config)])

        self.assertEqual(context.exception.code, "ARAZZO_VALIDATION_FAILED")

    def test_fails_for_invalid_actions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory),
                FIXTURES / "invalid" / "invalid-actions.yaml",
            )

            with self.assertRaises(ToolError) as context:
                run(["validate-arazzo", "--config", str(config)])

        self.assertEqual(context.exception.code, "ARAZZO_VALIDATION_FAILED")

    def test_fails_for_invalid_workflow_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory),
                FIXTURES / "invalid" / "invalid-workflow-inputs.yaml",
            )

            with self.assertRaises(ToolError) as context:
                run(["validate-arazzo", "--config", str(config)])

        self.assertEqual(context.exception.code, "ARAZZO_VALIDATION_FAILED")

    def test_fails_for_invalid_step_output_references(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory),
                FIXTURES / "invalid" / "invalid-step-output-references.yaml",
            )

            with self.assertRaises(ToolError) as context:
                run(["validate-arazzo", "--config", str(config)])

        self.assertEqual(context.exception.code, "ARAZZO_VALIDATION_FAILED")

    def test_fails_for_unconditional_control_flow_cycles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory),
                FIXTURES / "invalid" / "invalid-control-flow.yaml",
            )

            with self.assertRaises(ToolError) as context:
                run(["validate-arazzo", "--config", str(config)])

        self.assertEqual(context.exception.code, "ARAZZO_VALIDATION_FAILED")

    def test_fails_for_invalid_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory),
                FIXTURES / "invalid" / "invalid-dependencies.yaml",
            )

            with self.assertRaises(ToolError) as context:
                run(["validate-arazzo", "--config", str(config)])

        self.assertEqual(context.exception.code, "ARAZZO_VALIDATION_FAILED")

    def test_fails_for_invalid_step_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory),
                FIXTURES / "invalid" / "invalid-step-timeout.yaml",
            )

            with self.assertRaises(ToolError) as context:
                run(["validate-arazzo", "--config", str(config)])

        self.assertEqual(context.exception.code, "ARAZZO_VALIDATION_FAILED")

    def test_validate_all_resolves_local_openapi_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "tool.yaml"
            config.write_text(
                "\n".join(
                    (
                        "openapi:",
                        f"  - {CROSS_FIXTURES / 'valid' / 'openapi.yaml'}",
                        "arazzo:",
                        f"  - {CROSS_FIXTURES / 'valid' / 'workflow.yaml'}",
                        "security:",
                        f"  allowedRefRoots:\n    - {CROSS_FIXTURES}",
                        "",
                    )
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                run(["validate-all", "--config", str(config)]), ExitCode.SUCCESS
            )

    def test_validate_all_rejects_remote_openapi_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "tool.yaml"
            config.write_text(
                "\n".join(
                    (
                        "openapi:",
                        f"  - {CROSS_FIXTURES / 'valid' / 'openapi.yaml'}",
                        "arazzo:",
                        f"  - {CROSS_FIXTURES / 'invalid' / 'remote-source.yaml'}",
                        "security:",
                        f"  allowedRefRoots:\n    - {CROSS_FIXTURES}",
                        "",
                    )
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ToolError) as context:
                run(["validate-all", "--config", str(config)])

        self.assertEqual(context.exception.code, "CROSS_VALIDATION_FAILED")
