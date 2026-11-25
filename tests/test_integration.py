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

import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from tools.openapi_arazzo_tool.errors import ToolError
from tools.openapi_arazzo_tool.integration import main, verify_checkout


class IntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.url = "https://github.com/example/api-ncpeh.git"
        self._git("init", "-q")
        self._git("remote", "add", "origin", self.url)
        (self.root / "api.yaml").write_text(
            "openapi: 3.1.0\ninfo: {title: Widgets, version: 1.0.0}\n"
            "paths:\n  /widgets:\n    get:\n      operationId: listWidgets\n"
            "      responses:\n        '200': {description: OK}\n",
            encoding="utf-8",
        )
        (self.root / "workflow.yaml").write_text(
            "arazzo: 1.1.0\ninfo: {title: Widgets, version: 1.0.0}\n"
            "sourceDescriptions:\n  - {name: api, url: ./api.yaml, type: openapi}\n"
            "workflows:\n  - workflowId: list-widgets\n    steps:\n"
            "      - {stepId: list, operationId: listWidgets}\n",
            encoding="utf-8",
        )
        self._git("add", "api.yaml", "workflow.yaml")
        self._git(
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.test",
            "commit",
            "-qm",
            "initial",
        )
        self._git("tag", "v1.0.0")
        self.config = self.root.parent / f"{self.root.name}-tool.yaml"
        self.addCleanup(self.config.unlink, missing_ok=True)
        self.config.write_text(
            yaml.safe_dump(
                {
                    "openapi": [str(self.root / "api.yaml")],
                    "arazzo": [str(self.root / "workflow.yaml")],
                    "security": {"allowedRefRoots": [str(self.root)]},
                }
            ),
            encoding="utf-8",
        )

    def _git(self, *arguments: str) -> None:
        result = subprocess.run(
            ["git", "-C", str(self.root), *arguments], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_validates_tagged_checkout_and_sources(self) -> None:
        root, _, sha = verify_checkout(
            str(self.root), self.url, "v1.0.0", str(self.config)
        )
        self.assertEqual(root, self.root.resolve())
        self.assertEqual(len(sha), 40)
        self.assertEqual(
            main(
                [
                    "--checkout",
                    str(self.root),
                    "--repository-url",
                    self.url,
                    "--tag",
                    "v1.0.0",
                    "--config",
                    str(self.config),
                ]
            ),
            0,
        )

    def test_rejects_wrong_origin_tag_and_modified_worktree(self) -> None:
        for url, tag in ((self.url + "/other", "v1.0.0"), (self.url, "v2.0.0")):
            with self.subTest(url=url, tag=tag), self.assertRaises(ToolError):
                verify_checkout(str(self.root), url, tag, str(self.config))
        (self.root / "api.yaml").write_text("changed", encoding="utf-8")
        with self.assertRaises(ToolError):
            verify_checkout(str(self.root), self.url, "v1.0.0", str(self.config))

    def test_rejects_specs_outside_verified_checkout(self) -> None:
        self.config.write_text(
            yaml.safe_dump(
                {
                    "openapi": [str(self.config)],
                    "arazzo": [str(self.root / "workflow.yaml")],
                    "security": {"allowedRefRoots": [str(self.root)]},
                }
            ),
            encoding="utf-8",
        )
        with self.assertRaises(ToolError):
            verify_checkout(str(self.root), self.url, "v1.0.0", str(self.config))
