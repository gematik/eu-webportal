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

"""Secure local $ref resolution for OpenAPI documents.

Only local files are supported. Every resolution step is canonicalized and
checked against an explicit allowlist of root directories before the file is
read, per the security requirements in
docs/openapi-arazzo-mocking-test-tool-requirements.md (Kap. 17) and the
design recorded in docs/adr/ADR-0009-ref-resolution-strategy.md.

Relative paths are resolved directly against the real, potentially deeply
nested directory structure of the referencing file. No flattening or
virtual working directory is used. Arbitrarily many ``../`` segments are
supported as long as the canonical (fully resolved) target stays within an
allowed root; this is the standard defense against path traversal: never
trust the raw path string, always canonicalize first and only then check
containment.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..errors import ExitCode, ToolError

_REMOTE_SCHEME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://")


@dataclass(frozen=True)
class ResolvedRef:
    """Result of resolving a single ``$ref`` value."""

    file_path: Path
    fragment: str
    value: Any


def split_ref(ref: str) -> tuple[str, str]:
    """Split a $ref value into its file part and JSON pointer fragment."""
    index = ref.find("#")
    if index == -1:
        return ref, ""
    return ref[:index], ref[index:]


def resolve_json_pointer(
    document: Any, fragment: str, *, ref: str, file_label: str
) -> Any:
    """Resolve an RFC 6901 JSON pointer fragment against a parsed document."""
    pointer = fragment[1:] if fragment.startswith("#") else fragment
    if pointer.startswith("/"):
        pointer = pointer[1:]

    node = document
    if pointer == "":
        return node

    for raw_segment in pointer.split("/"):
        segment = raw_segment.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict):
            if segment not in node:
                raise ToolError(
                    "OPENAPI_REF_UNRESOLVED",
                    f"Reference '{ref}' points to a non-existent path '{fragment}' in {file_label}.",
                    ExitCode.VALIDATION_ERROR,
                    file_label,
                )
            node = node[segment]
        elif isinstance(node, list):
            try:
                node = node[int(segment)]
            except (ValueError, IndexError) as error:
                raise ToolError(
                    "OPENAPI_REF_UNRESOLVED",
                    f"Reference '{ref}' points to a non-existent path '{fragment}' in {file_label}.",
                    ExitCode.VALIDATION_ERROR,
                    file_label,
                ) from error
        else:
            raise ToolError(
                "OPENAPI_REF_UNRESOLVED",
                f"Reference '{ref}' cannot descend into a scalar value at '{fragment}' in {file_label}.",
                ExitCode.VALIDATION_ERROR,
                file_label,
            )

    return node


def _canonical_roots(allowed_roots: list[str]) -> list[Path]:
    return [Path(root).resolve() for root in allowed_roots]


def _is_within_roots(path: Path, roots: list[Path]) -> bool:
    return any(path == root or root in path.parents for root in roots)


def resolve_ref(
    base_document: dict[str, Any],
    base_path: str,
    ref: str,
    allowed_roots: list[str],
) -> ResolvedRef:
    """Resolve a single $ref relative to the document that contains it.

    ``base_document`` is the already-parsed content of ``base_path`` and is
    used directly for refs that only contain a fragment (``#/...``), so that
    same-document references never touch the filesystem.
    """
    file_part, fragment = split_ref(ref)

    if file_part == "":
        value = resolve_json_pointer(
            base_document, fragment, ref=ref, file_label=base_path
        )
        return ResolvedRef(file_path=Path(base_path), fragment=fragment, value=value)

    if _REMOTE_SCHEME_PATTERN.match(file_part) or file_part.startswith("file:"):
        raise ToolError(
            "OPENAPI_REF_FORBIDDEN",
            f"Remote reference '{ref}' is not allowed. Only local files are supported in V1.",
            ExitCode.VALIDATION_ERROR,
            base_path,
        )

    if Path(file_part).is_absolute():
        raise ToolError(
            "OPENAPI_REF_FORBIDDEN",
            f"Absolute reference path '{ref}' is not allowed.",
            ExitCode.VALIDATION_ERROR,
            base_path,
        )

    candidate = (Path(base_path).resolve().parent / file_part).resolve()
    roots = _canonical_roots(allowed_roots)

    if not _is_within_roots(candidate, roots):
        raise ToolError(
            "OPENAPI_REF_FORBIDDEN",
            f"Reference '{ref}' resolves outside the allowed root directories.",
            ExitCode.VALIDATION_ERROR,
            base_path,
        )

    if not candidate.exists():
        raise ToolError(
            "OPENAPI_REF_UNRESOLVED",
            f"Reference '{ref}' points to a file that does not exist: {candidate}",
            ExitCode.VALIDATION_ERROR,
            base_path,
        )

    target_document = parse_referenced_file(candidate, ref=ref, file_label=base_path)
    value = resolve_json_pointer(
        target_document, fragment, ref=ref, file_label=str(candidate)
    )
    return ResolvedRef(file_path=candidate, fragment=fragment, value=value)


def parse_referenced_file(path: Path, *, ref: str, file_label: str) -> Any:
    """Parse a local YAML/JSON file, translating I/O and syntax errors into
    a stable ``OPENAPI_REF_UNRESOLVED`` diagnostic."""
    try:
        with path.open(encoding="utf-8") as stream:
            return yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as error:
        raise ToolError(
            "OPENAPI_REF_UNRESOLVED",
            f"Unable to parse referenced file '{path}': {error}",
            ExitCode.VALIDATION_ERROR,
            file_label,
        ) from error


def find_ref_issues(document: Any, allowed_roots: list[str]) -> list[ToolError]:
    """Walk an entire OpenAPI document and resolve every ``$ref`` found,
    including refs nested inside other referenced files.

    Every unique ``(file, fragment)`` target is validated exactly once,
    which guarantees termination even for legitimate recursive or mutually
    referencing schemas (a normal and allowed JSON Schema/OpenAPI construct,
    e.g. a tree-shaped ``Node`` schema referencing itself). Such recursion is
    NOT treated as an error; only unresolved or forbidden references are
    reported.

    Returns a list of issues (empty if every reachable ``$ref`` resolves
    within the allowed root directories). Nothing is raised directly so that
    callers can aggregate all problems found across a whole document instead
    of stopping at the first one.
    """
    root_path = Path(document.path).resolve()
    document_cache: dict[Path, Any] = {root_path: document.raw}
    visited: set[tuple[Path, str]] = set()
    issues: list[ToolError] = []

    _walk_refs(
        document.raw, root_path, "$", document_cache, visited, issues, allowed_roots
    )
    return issues


def _walk_refs(
    node: Any,
    current_file: Path,
    json_path: str,
    document_cache: dict[Path, Any],
    visited: set[tuple[Path, str]],
    issues: list[ToolError],
    allowed_roots: list[str],
) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str):
            _walk_single_ref(
                ref,
                current_file,
                json_path,
                document_cache,
                visited,
                issues,
                allowed_roots,
            )
        # OpenAPI 3.1 (JSON Schema 2020-12) permits sibling keys next to
        # $ref; walk them too instead of assuming $ref is exclusive.
        for key, value in node.items():
            if key == "$ref":
                continue
            _walk_refs(
                value,
                current_file,
                f"{json_path}.{key}",
                document_cache,
                visited,
                issues,
                allowed_roots,
            )
    elif isinstance(node, list):
        for index, item in enumerate(node):
            _walk_refs(
                item,
                current_file,
                f"{json_path}[{index}]",
                document_cache,
                visited,
                issues,
                allowed_roots,
            )


def _walk_single_ref(
    ref: str,
    current_file: Path,
    json_path: str,
    document_cache: dict[Path, Any],
    visited: set[tuple[Path, str]],
    issues: list[ToolError],
    allowed_roots: list[str],
) -> None:
    current_document = document_cache[current_file]

    try:
        resolved = resolve_ref(current_document, str(current_file), ref, allowed_roots)
    except ToolError as error:
        issues.append(
            ToolError(
                error.code,
                f"{error.message} (found at {json_path})",
                error.exit_code,
                error.file,
            )
        )
        return

    target_file = resolved.file_path.resolve()
    visit_key = (target_file, resolved.fragment)
    if visit_key in visited:
        return
    visited.add(visit_key)

    if target_file not in document_cache:
        try:
            document_cache[target_file] = parse_referenced_file(
                target_file, ref=ref, file_label=str(current_file)
            )
        except ToolError as error:
            issues.append(
                ToolError(
                    error.code,
                    f"{error.message} (found at {json_path})",
                    error.exit_code,
                    error.file,
                )
            )
            return

    _walk_refs(
        resolved.value,
        target_file,
        f"{json_path} -> {ref}",
        document_cache,
        visited,
        issues,
        allowed_roots,
    )
