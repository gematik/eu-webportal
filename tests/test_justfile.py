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

"""Tests keeping the justfile aligned with the actual CLI surface.

The justfile is the documented entry point for local and CI usage. A recipe
that invokes a command the CLI does not know fails only when somebody runs it,
so the mapping is asserted here instead.
"""

import re
import unittest
from pathlib import Path

from tools.openapi_arazzo_tool.cli import COMMANDS

ROOT = Path(__file__).resolve().parents[1]
JUSTFILE = ROOT / "justfile"

# Commands that are intentionally not exposed as a recipe.
UNEXPOSED_COMMANDS = frozenset({"explain"})


def _justfile() -> str:
    return JUSTFILE.read_text(encoding="utf-8")


def _recipe_names(content: str) -> set[str]:
    return {
        match.group(1)
        for match in re.finditer(
            r"^([a-z][a-z0-9-]*)(?: [^:]*)?:(?!=)", content, re.MULTILINE
        )
    }


class JustfileCommandCoverageTest(unittest.TestCase):
    def test_every_implemented_command_has_a_recipe(self) -> None:
        content = _justfile()
        for command in COMMANDS:
            if command in UNEXPOSED_COMMANDS:
                continue
            with self.subTest(command=command):
                self.assertRegex(content, rf"\{{\{{cli\}}\}} {re.escape(command)}\b")

    def test_does_not_invoke_unknown_commands(self) -> None:
        invoked = set(re.findall(r"\{\{cli\}\} ([a-z][a-z-]*)", _justfile()))
        self.assertEqual(invoked - set(COMMANDS) - {"--help"}, set())

    def test_unimplemented_command_is_not_exposed(self) -> None:
        self.assertNotIn("explain", _recipe_names(_justfile()))


class JustfileStructureTest(unittest.TestCase):
    def test_declares_windows_shell(self) -> None:
        self.assertIn('set windows-shell := ["powershell"', _justfile())

    def test_lives_at_the_repository_root(self) -> None:
        # `just` searches upwards from the current directory, so a justfile in
        # a subdirectory is invisible from the root and from sibling folders.
        # Recipes also invoke `python -m tools.openapi_arazzo_tool...`, which
        # only resolves from the root.
        self.assertEqual(JUSTFILE.parent, ROOT)
        self.assertNotIn("set working-directory", _justfile())
        self.assertTrue((ROOT / "pyproject.toml").is_file())

    def test_default_recipe_lists_available_recipes(self) -> None:
        self.assertRegex(_justfile(), r"(?m)^default:\n\s+@just --list")

    def test_exposes_docker_and_integration_entrypoints(self) -> None:
        names = _recipe_names(_justfile())
        self.assertIn("docker-build", names)
        self.assertIn("docker-run", names)
        self.assertIn("verify-checkout", names)

    def test_unit_recipe_uses_unittest(self) -> None:
        self.assertIn("python -m unittest discover -s tests", _justfile())

    def test_package_recipe_uses_package_directory_and_runtime_overrides(self) -> None:
        content = _justfile()
        self.assertIn("start-mock-package package_dir *arguments:", content)
        self.assertIn(
            '{{cli}} start-mocks --package-dir "{{package_dir}}" {{arguments}}',
            content,
        )

    def test_uses_no_posix_line_continuations(self) -> None:
        self.assertNotIn("\\\n", _justfile())


class PyprojectConsistencyTest(unittest.TestCase):
    def test_does_not_configure_an_unused_test_runner(self) -> None:
        content = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertNotIn("pytest", content)


if __name__ == "__main__":
    unittest.main()
