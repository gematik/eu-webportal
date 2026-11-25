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

FIXTURES = Path(__file__).parent / "fixtures" / "openapi"


class ValidateOpenApiCliTest(unittest.TestCase):
    def _write_config(
        self,
        directory: Path,
        *openapi_paths: Path,
        allowed_ref_roots: list[Path] | None = None,
    ) -> Path:
        config = directory / "tool.yaml"
        openapi_entries = "\n".join(f"  - {path}" for path in openapi_paths)
        roots = allowed_ref_roots if allowed_ref_roots is not None else [FIXTURES]
        root_entries = "\n".join(f"  - {root}" for root in roots)
        config.write_text(
            f"openapi:\n{openapi_entries}\nsecurity:\n  allowedRefRoots:\n{root_entries}\n",
            encoding="utf-8",
        )
        return config

    def test_succeeds_for_valid_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory), FIXTURES / "valid" / "minimal-3.1.yaml"
            )
            self.assertEqual(
                run(["validate-openapi", "--config", str(config)]), ExitCode.SUCCESS
            )

    def test_fails_for_unsupported_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory), FIXTURES / "invalid" / "version-3.0.yaml"
            )
            with self.assertRaises(ToolError) as context:
                run(["validate-openapi", "--config", str(config)])
        self.assertEqual(context.exception.code, "OPENAPI_VALIDATION_FAILED")
        self.assertEqual(context.exception.exit_code, ExitCode.VALIDATION_ERROR)

    def test_fails_when_no_documents_configured(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "tool.yaml"
            config.write_text(
                f"openapi: []\nsecurity:\n  allowedRefRoots:\n  - {FIXTURES}\n",
                encoding="utf-8",
            )
            with self.assertRaises(ToolError) as context:
                run(["validate-openapi", "--config", str(config)])
        self.assertEqual(context.exception.code, "CONFIG_INVALID")
        self.assertEqual(context.exception.exit_code, ExitCode.CONFIGURATION_ERROR)

    def test_fails_when_no_allowed_ref_roots_configured(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "tool.yaml"
            config.write_text(
                f"openapi:\n  - {FIXTURES / 'valid' / 'minimal-3.1.yaml'}\n",
                encoding="utf-8",
            )
            with self.assertRaises(ToolError) as context:
                run(["validate-openapi", "--config", str(config)])
        self.assertEqual(context.exception.code, "CONFIG_INVALID")
        self.assertEqual(context.exception.exit_code, ExitCode.CONFIGURATION_ERROR)

    def test_fails_for_unresolved_ref_chain(self) -> None:
        refs_dir = FIXTURES / "refs" / "chain"
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory),
                refs_dir / "root-broken.yaml",
                allowed_ref_roots=[refs_dir],
            )
            with self.assertRaises(ToolError) as context:
                run(["validate-openapi", "--config", str(config)])
        self.assertEqual(context.exception.code, "OPENAPI_VALIDATION_FAILED")

    def test_fails_for_duplicate_operation_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory),
                FIXTURES / "invalid" / "duplicate-operation-id.yaml",
            )
            with self.assertRaises(ToolError) as context:
                run(["validate-openapi", "--config", str(config)])
        self.assertEqual(context.exception.code, "OPENAPI_VALIDATION_FAILED")

    def test_fails_for_invalid_json_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory),
                FIXTURES / "invalid" / "invalid-json-schema.yaml",
            )
            with self.assertRaises(ToolError) as context:
                run(["validate-openapi", "--config", str(config)])
        self.assertEqual(context.exception.code, "OPENAPI_VALIDATION_FAILED")

    def test_fails_for_invalid_document_structure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory),
                FIXTURES / "invalid" / "invalid-document-structure.yaml",
            )
            with self.assertRaises(ToolError) as context:
                run(["validate-openapi", "--config", str(config)])
        self.assertEqual(context.exception.code, "OPENAPI_VALIDATION_FAILED")

    def test_fails_for_invalid_parameters(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory),
                FIXTURES / "invalid" / "invalid-parameters.yaml",
            )
            with self.assertRaises(ToolError) as context:
                run(["validate-openapi", "--config", str(config)])
        self.assertEqual(context.exception.code, "OPENAPI_VALIDATION_FAILED")

    def test_fails_for_invalid_responses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory),
                FIXTURES / "invalid" / "invalid-responses.yaml",
            )
            with self.assertRaises(ToolError) as context:
                run(["validate-openapi", "--config", str(config)])
        self.assertEqual(context.exception.code, "OPENAPI_VALIDATION_FAILED")

    def test_fails_for_invalid_request_bodies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory),
                FIXTURES / "invalid" / "invalid-request-bodies.yaml",
            )
            with self.assertRaises(ToolError) as context:
                run(["validate-openapi", "--config", str(config)])
        self.assertEqual(context.exception.code, "OPENAPI_VALIDATION_FAILED")

    def test_fails_for_invalid_security(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory),
                FIXTURES / "invalid" / "invalid-security.yaml",
            )
            with self.assertRaises(ToolError) as context:
                run(["validate-openapi", "--config", str(config)])
        self.assertEqual(context.exception.code, "OPENAPI_VALIDATION_FAILED")

    def test_fails_for_invalid_examples(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = self._write_config(
                Path(directory),
                FIXTURES / "invalid" / "invalid-examples.yaml",
            )
            with self.assertRaises(ToolError) as context:
                run(["validate-openapi", "--config", str(config)])
        self.assertEqual(context.exception.code, "OPENAPI_VALIDATION_FAILED")
