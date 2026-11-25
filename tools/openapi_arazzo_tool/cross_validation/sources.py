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

"""Secure local resolution of Arazzo OpenAPI source descriptions."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeGuard

from ..arazzo.model import ArazzoDocument
from ..errors import ExitCode, ToolError
from ..openapi.examples import find_example_issues
from ..openapi.loader import load_openapi_document
from ..openapi.operations import find_operation_id_issues
from ..openapi.parameters import find_parameter_issues
from ..openapi.refs import find_ref_issues
from ..openapi.request_bodies import find_request_body_issues
from ..openapi.responses import find_response_issues
from ..openapi.schemas import find_schema_issues
from ..openapi.security import find_security_issues
from ..openapi.structure import find_structure_issues

_URI_SCHEME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*:")


@dataclass(frozen=True)
class ResolvedSources:
    """Locally loaded OpenAPI source descriptions and their diagnostics."""

    sources: dict[str, Any]
    issues: list[ToolError]


def find_source_issues(
    document: ArazzoDocument, allowed_roots: list[str]
) -> list[ToolError]:
    """Resolve and validate every supported local OpenAPI source description."""
    return resolve_sources(document, allowed_roots).issues


def resolve_sources(
    document: ArazzoDocument, allowed_roots: list[str]
) -> ResolvedSources:
    """Resolve valid local OpenAPI sources for cross-validation consumers."""
    sources = document.raw.get("sourceDescriptions")
    if not _is_sequence(sources):
        return ResolvedSources({}, [])

    issues: list[ToolError] = []
    resolved_sources: dict[str, Any] = {}
    for index, source in enumerate(sources):
        if not isinstance(source, Mapping) or source.get("type") != "openapi":
            continue
        path = f"$.sourceDescriptions[{index}].url"
        url = source.get("url")
        if not isinstance(url, str) or not url.strip():
            continue
        source_path = _resolve_source_path(
            url, document.path, allowed_roots, path, issues
        )
        if source_path is None:
            continue
        loaded_source = _validate_source_document(
            source_path, allowed_roots, path, issues
        )
        name = source.get("name")
        if loaded_source is not None and isinstance(name, str) and name:
            resolved_sources[name] = loaded_source
    return ResolvedSources(resolved_sources, issues)


def _resolve_source_path(
    url: str,
    arazzo_path: str,
    allowed_roots: list[str],
    path: str,
    issues: list[ToolError],
) -> Path | None:
    if "#" in url:
        _add_issue(
            issues,
            "ARAZZO_SOURCE_UNRESOLVED",
            path,
            "Source Description URL must not contain a fragment.",
            arazzo_path,
        )
        return None
    if _URI_SCHEME_PATTERN.match(url) or Path(url).is_absolute():
        _add_issue(
            issues,
            "ARAZZO_SOURCE_FORBIDDEN",
            path,
            "Only local relative Source Description URLs are supported in V1.",
            arazzo_path,
        )
        return None

    candidate = (Path(arazzo_path).resolve().parent / url).resolve()
    roots = [Path(root).resolve() for root in allowed_roots]
    if not any(candidate == root or root in candidate.parents for root in roots):
        _add_issue(
            issues,
            "ARAZZO_SOURCE_FORBIDDEN",
            path,
            f"Source Description URL '{url}' resolves outside the allowed root directories.",
            arazzo_path,
        )
        return None
    if not candidate.is_file():
        _add_issue(
            issues,
            "ARAZZO_SOURCE_UNRESOLVED",
            path,
            f"Source Description URL '{url}' does not resolve to a file.",
            arazzo_path,
        )
        return None
    return candidate


def _validate_source_document(
    source_path: Path,
    allowed_roots: list[str],
    source_path_in_arazzo: str,
    issues: list[ToolError],
) -> Any | None:
    try:
        source = load_openapi_document(str(source_path))
    except ToolError as load_error:
        _add_issue(
            issues,
            "ARAZZO_SOURCE_UNRESOLVED",
            source_path_in_arazzo,
            f"Unable to load referenced OpenAPI document: {load_error.message}",
            load_error.file or str(source_path),
        )
        return None

    openapi_issues = [
        *find_ref_issues(source, allowed_roots),
        *find_structure_issues(source),
        *find_operation_id_issues(source),
        *find_parameter_issues(source),
        *find_example_issues(source),
        *find_request_body_issues(source),
        *find_response_issues(source),
        *find_schema_issues(source),
        *find_security_issues(source),
    ]
    for error in openapi_issues:
        _add_issue(
            issues,
            "ARAZZO_SOURCE_INVALID",
            source_path_in_arazzo,
            f"Referenced OpenAPI document is invalid: {error.message}",
            error.file or str(source_path),
        )
    if openapi_issues:
        return None
    return source


def _is_sequence(value: Any) -> TypeGuard[Sequence[Any]]:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


def _add_issue(
    issues: list[ToolError], code: str, path: str, message: str, file_path: str
) -> None:
    issues.append(
        ToolError(
            code,
            f"{message} Found at {path}.",
            ExitCode.VALIDATION_ERROR,
            file_path,
        )
    )
