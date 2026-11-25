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

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import yaml

from tools.openapi_arazzo_tool.cli import run
from tools.openapi_arazzo_tool.errors import ExitCode, ToolError

FIXTURES = Path(__file__).parent / "fixtures" / "cross"


class ArazzoSecurityRequirementValidationTest(unittest.TestCase):
    def test_accepts_supported_or_alternative(self) -> None:
        self.assertEqual(self.validate_fixture("valid", "security"), ExitCode.SUCCESS)

    def test_accepts_mtls_single_and_and_requirements_without_runtime_support(
        self,
    ) -> None:
        self.assertEqual(
            self.validate_fixture("invalid", "unsupported-security"),
            ExitCode.SUCCESS,
        )

    def test_still_rejects_undefined_security_scheme(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = yaml.safe_load(
                (FIXTURES / "valid" / "security-openapi.yaml").read_text(
                    encoding="utf-8"
                )
            )
            source["security"] = [{"Unknown": []}]
            source_path = root / "api.yaml"
            source_path.write_text(yaml.safe_dump(source), encoding="utf-8")
            config = root / "tool.yaml"
            config.write_text(
                yaml.safe_dump(
                    {
                        "openapi": [str(source_path)],
                        "security": {"allowedRefRoots": [str(root)]},
                    }
                ),
                encoding="utf-8",
            )

            with (
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(ToolError) as error,
            ):
                run(["validate-openapi", "--config", str(config)])

            self.assertEqual(error.exception.code, "OPENAPI_VALIDATION_FAILED")

    def validate_fixture(self, category: str, prefix: str) -> int:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "tool.yaml"
            config.write_text(
                yaml.safe_dump(
                    {
                        "openapi": [
                            str(FIXTURES / category / f"{prefix}-openapi.yaml")
                        ],
                        "arazzo": [
                            str(FIXTURES / category / f"{prefix}-workflow.yaml")
                        ],
                        "security": {"allowedRefRoots": [str(FIXTURES)]},
                    }
                ),
                encoding="utf-8",
            )
            with contextlib.redirect_stdout(io.StringIO()):
                return run(["validate-all", "--config", str(config)])
