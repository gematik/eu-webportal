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

"""Arazzo 1.1 document structure and source-description validation."""

from collections.abc import Mapping, Sequence
from typing import Any

from ..errors import ExitCode, ToolError
from .model import ArazzoDocument

_KNOWN_SOURCE_TYPES = frozenset({"openapi", "asyncapi", "arazzo"})


def find_structure_issues(document: ArazzoDocument) -> list[ToolError]:
    """Validate Arazzo document boundaries before workflow semantics."""
    raw = document.raw
    issues: list[ToolError] = []
    _validate_info(raw.get("info"), document.path, issues)
    _validate_source_descriptions(raw.get("sourceDescriptions"), document.path, issues)
    _validate_workflows(raw.get("workflows"), document.path, issues)
    if "components" in raw:
        _add_unsupported_issue(
            issues, "$.components", "Arazzo components", document.path
        )
    return issues


def _validate_info(info: Any, file_path: str, issues: list[ToolError]) -> None:
    if not isinstance(info, Mapping):
        _add_structure_issue(
            issues, "$.info", "Info Object must be a mapping.", file_path
        )
        return
    _require_non_empty_string(
        info.get("title"), "$.info.title", "Info title", file_path, issues
    )
    _require_non_empty_string(
        info.get("version"), "$.info.version", "Info version", file_path, issues
    )


def _validate_source_descriptions(
    value: Any, file_path: str, issues: list[ToolError]
) -> None:
    path = "$.sourceDescriptions"
    if not _is_sequence(value):
        _add_structure_issue(
            issues, path, "sourceDescriptions must be an array.", file_path
        )
        return
    if not value:
        _add_structure_issue(
            issues,
            path,
            "sourceDescriptions must define at least one source.",
            file_path,
        )
        return

    names: set[str] = set()
    for index, source in enumerate(value):
        source_path = f"{path}[{index}]"
        if not isinstance(source, Mapping):
            _add_structure_issue(
                issues, source_path, "Source Description must be a mapping.", file_path
            )
            continue
        name = source.get("name")
        _require_non_empty_string(
            name, f"{source_path}.name", "Source Description name", file_path, issues
        )
        if isinstance(name, str) and name.strip():
            if name in names:
                _add_structure_issue(
                    issues,
                    f"{source_path}.name",
                    f"Source Description name '{name}' must be unique.",
                    file_path,
                )
            names.add(name)
        _require_non_empty_string(
            source.get("url"),
            f"{source_path}.url",
            "Source Description URL",
            file_path,
            issues,
        )
        _validate_source_type(
            source.get("type"), f"{source_path}.type", file_path, issues
        )


def _validate_source_type(
    value: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if not isinstance(value, str) or not value.strip():
        _add_structure_issue(
            issues,
            path,
            "Source Description type must be a non-empty string.",
            file_path,
        )
    elif value == "openapi":
        return
    elif value in _KNOWN_SOURCE_TYPES:
        _add_unsupported_issue(
            issues, path, f"Source Description type '{value}'", file_path
        )
    else:
        _add_structure_issue(
            issues, path, f"Source Description type '{value}' is unknown.", file_path
        )


def _validate_workflows(value: Any, file_path: str, issues: list[ToolError]) -> None:
    path = "$.workflows"
    if not _is_sequence(value):
        _add_structure_issue(issues, path, "workflows must be an array.", file_path)
    elif not value:
        _add_structure_issue(
            issues, path, "workflows must define at least one workflow.", file_path
        )


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


def _require_non_empty_string(
    value: Any, path: str, label: str, file_path: str, issues: list[ToolError]
) -> None:
    if not isinstance(value, str) or not value.strip():
        _add_structure_issue(
            issues, path, f"{label} must be a non-empty string.", file_path
        )


def _add_structure_issue(
    issues: list[ToolError], path: str, message: str, file_path: str
) -> None:
    issues.append(
        ToolError(
            "ARAZZO_STRUCTURE_INVALID",
            f"{message} Found at {path}.",
            ExitCode.VALIDATION_ERROR,
            file_path,
        )
    )


def _add_unsupported_issue(
    issues: list[ToolError], path: str, feature: str, file_path: str
) -> None:
    issues.append(
        ToolError(
            "ARAZZO_FEATURE_UNSUPPORTED",
            f"{feature} is not supported in V1. Found at {path}.",
            ExitCode.VALIDATION_ERROR,
            file_path,
        )
    )
