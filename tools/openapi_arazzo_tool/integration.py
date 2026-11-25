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

"""Validate an externally authenticated, tag-pinned integration checkout."""

import argparse
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

from .cli import _validate_all
from .config import load_config
from .errors import ExitCode, ToolError


def _git(checkout: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(checkout), *arguments],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise ToolError(
            "INTEGRATION_INVALID", "Git is unavailable.", ExitCode.CONFIGURATION_ERROR
        ) from error
    if result.returncode:
        raise ToolError(
            "INTEGRATION_INVALID",
            "Checkout does not satisfy the requested Git metadata.",
            ExitCode.CONFIGURATION_ERROR,
        )
    return result.stdout.strip()


def verify_checkout(
    checkout: str,
    repository_url: str,
    tag: str,
    config_path: str,
) -> tuple[Path, dict, str]:
    """Ensure trusted automation supplied the exact clean tag and allowed roots."""
    root = Path(checkout).resolve()
    if not root.is_dir() or not repository_url or not tag:
        raise ToolError(
            "INTEGRATION_INVALID",
            "Checkout, repository URL and tag are required.",
            ExitCode.CONFIGURATION_ERROR,
        )
    parsed = urlsplit(repository_url)
    if parsed.username or parsed.password:
        raise ToolError(
            "INTEGRATION_INVALID",
            "Repository URL must not embed credentials.",
            ExitCode.CONFIGURATION_ERROR,
        )
    if Path(_git(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise ToolError(
            "INTEGRATION_INVALID",
            "Checkout must be the repository root.",
            ExitCode.CONFIGURATION_ERROR,
        )
    if _git(root, "remote", "get-url", "origin") != repository_url:
        raise ToolError(
            "INTEGRATION_INVALID",
            "Checkout origin differs from supplied repository URL.",
            ExitCode.CONFIGURATION_ERROR,
        )
    _git(root, "check-ref-format", f"refs/tags/{tag}")
    head = _git(root, "rev-parse", "--verify", "HEAD")
    tagged = _git(root, "rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}")
    if head != tagged or _git(root, "status", "--porcelain"):
        raise ToolError(
            "INTEGRATION_INVALID",
            "Checkout must be clean and match the requested Git tag.",
            ExitCode.CONFIGURATION_ERROR,
        )
    config = load_config(config_path)
    security = config.get("security")
    roots = security.get("allowedRefRoots") if isinstance(security, dict) else None
    if (
        not isinstance(roots, list)
        or not roots
        or any(
            not isinstance(item, str) or Path(item).resolve() != root for item in roots
        )
    ):
        raise ToolError(
            "INTEGRATION_INVALID",
            "security.allowedRefRoots must contain only the verified checkout.",
            ExitCode.CONFIGURATION_ERROR,
        )
    for key in ("openapi", "arazzo"):
        paths = config.get(key)
        if (
            not isinstance(paths, list)
            or not paths
            or any(
                not isinstance(item, str) or root not in Path(item).resolve().parents
                for item in paths
            )
        ):
            raise ToolError(
                "INTEGRATION_INVALID",
                f"All {key} documents must be inside the verified checkout.",
                ExitCode.CONFIGURATION_ERROR,
            )
    return root, config, head


def main(arguments: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a JSL-provided Git-tag checkout."
    )
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--repository-url", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--config", required=True)
    args = parser.parse_args(arguments)
    try:
        _, config, sha = verify_checkout(
            args.checkout, args.repository_url, args.tag, args.config
        )
        _validate_all(config)
        print(f"Validated tag {args.tag} at commit {sha}")
        return ExitCode.SUCCESS
    except ToolError as error:
        print(error, file=sys.stderr)
        return error.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
