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

import json
import tempfile
import unittest
from pathlib import Path

from tools.check_versions import validate_versions


class VersionValidationTest(unittest.TestCase):
    def create_repository(self, portal_version: str = "0.0.0") -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / "frontend").mkdir()

        (root / "versions.toml").write_text(
            '[project]\nversion = "0.1.0"\n'
            '[portal]\nversion = "0.0.0"\n'
            '[python-tools]\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        (root / "frontend" / "package.json").write_text(
            json.dumps({"version": portal_version}), encoding="utf-8"
        )
        (root / "frontend" / "package-lock.json").write_text(
            json.dumps(
                {
                    "version": portal_version,
                    "packages": {"": {"version": portal_version}},
                }
            ),
            encoding="utf-8",
        )
        (root / "pyproject.toml").write_text(
            '[project]\nname = "openapi-arazzo-tool"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        (root / "uv.lock").write_text(
            'version = 1\n[[package]]\nname = "openapi-arazzo-tool"\n'
            'version = "0.1.0"\n',
            encoding="utf-8",
        )
        return root

    def test_validate_versions_returns_central_versions_when_manifests_match(
        self,
    ) -> None:
        self.assertEqual(
            validate_versions(self.create_repository()),
            {"project": "0.1.0", "portal": "0.0.0", "python-tools": "0.1.0"},
        )

    def test_validate_versions_rejects_mismatched_portal_version(self) -> None:
        with self.assertRaisesRegex(ValueError, "frontend/package.json is 0.1.0"):
            validate_versions(self.create_repository(portal_version="0.1.0"))

    def test_validate_versions_rejects_invalid_semver(self) -> None:
        root = self.create_repository()
        versions = root / "versions.toml"
        versions.write_text(
            versions.read_text(encoding="utf-8").replace(
                'version = "0.1.0"', 'version = "01.1.0"', 1
            ),
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "valid SemVer"):
            validate_versions(root)
