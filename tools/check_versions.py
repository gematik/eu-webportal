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

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SEMVER_PATTERN = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


def _read_version(value: Any, source: str) -> str:
    if not isinstance(value, str) or not SEMVER_PATTERN.fullmatch(value):
        raise ValueError(f"{source} must contain a valid SemVer version.")
    return value


def _read_section(data: dict[str, Any], name: str, source: str) -> dict[str, Any]:
    section = data.get(name)
    if not isinstance(section, dict):
        raise ValueError(f"{source} must contain a [{name}] section.")
    return section


def _read_object(value: Any, source: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{source} must contain a JSON object.")
    return value


def _read_uv_lock_version(lock_data: dict[str, Any], package_name: str) -> str:
    packages = lock_data.get("package")
    if not isinstance(packages, list):
        raise ValueError("uv.lock must contain a package list.")
    matches = [
        package
        for package in packages
        if isinstance(package, dict) and package.get("name") == package_name
    ]
    if len(matches) != 1:
        raise ValueError(
            f"uv.lock must contain exactly one package named {package_name!r}."
        )
    return _read_version(matches[0].get("version"), "uv.lock")


def validate_versions(root: Path = ROOT) -> dict[str, str]:
    with (root / "versions.toml").open("rb") as file:
        central = tomllib.load(file)
    with (root / "frontend" / "package.json").open(encoding="utf-8") as file:
        package = _read_object(json.load(file), "package.json")
    with (root / "frontend" / "package-lock.json").open(encoding="utf-8") as file:
        package_lock = _read_object(json.load(file), "package-lock.json")
    with (root / "pyproject.toml").open("rb") as file:
        python_project = tomllib.load(file)
    with (root / "uv.lock").open("rb") as file:
        uv_lock = tomllib.load(file)

    project_data = _read_section(central, "project", "versions.toml")
    portal_data = _read_section(central, "portal", "versions.toml")
    python_tools_data = _read_section(central, "python-tools", "versions.toml")
    python_project_data = _read_section(python_project, "project", "pyproject.toml")
    package_lock_packages = package_lock.get("packages")
    if not isinstance(package_lock_packages, dict):
        raise ValueError("package-lock.json must contain a packages object.")
    package_lock_root = _read_object(
        package_lock_packages.get(""), 'package-lock.json packages[""]'
    )
    python_package_name = python_project_data.get("name")
    if not isinstance(python_package_name, str) or not python_package_name:
        raise ValueError("pyproject.toml must define a project name.")

    project_version = _read_version(
        project_data.get("version"), "versions.toml [project]"
    )
    portal_version = _read_version(portal_data.get("version"), "versions.toml [portal]")
    python_tools_version = _read_version(
        python_tools_data.get("version"),
        "versions.toml [python-tools]",
    )

    manifest_versions = {
        "frontend/package.json": _read_version(package.get("version"), "package.json"),
        "frontend/package-lock.json": _read_version(
            package_lock_root.get("version"),
            'package-lock.json packages[""]',
        ),
        "frontend/package-lock.json root": _read_version(
            package_lock.get("version"), "package-lock.json"
        ),
        "pyproject.toml": _read_version(
            python_project_data.get("version"), "pyproject.toml"
        ),
        "uv.lock": _read_uv_lock_version(uv_lock, python_package_name),
    }

    expected_versions = {
        "frontend/package.json": portal_version,
        "frontend/package-lock.json": portal_version,
        "frontend/package-lock.json root": portal_version,
        "pyproject.toml": python_tools_version,
        "uv.lock": python_tools_version,
    }
    mismatches = [
        f"{source} is {actual}, expected {expected_versions[source]}"
        for source, actual in manifest_versions.items()
        if actual != expected_versions[source]
    ]
    if mismatches:
        raise ValueError("; ".join(mismatches))

    return {
        "project": project_version,
        "portal": portal_version,
        "python-tools": python_tools_version,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate centralized versions.")
    parser.add_argument(
        "--project-version",
        action="store_true",
        help="Print validated project version for Jenkins tagging.",
    )
    arguments = parser.parse_args()

    try:
        versions = validate_versions()
    except (
        OSError,
        KeyError,
        json.JSONDecodeError,
        tomllib.TOMLDecodeError,
        ValueError,
    ) as error:
        print(f"Version validation failed: {error}", file=sys.stderr)
        return 1

    if arguments.project_version:
        print(versions["project"])
    else:
        print("Central and manifest versions match.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
