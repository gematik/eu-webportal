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

"""Bundling of cross-file ``$ref`` values into a single OpenAPI document.

Validation resolves references in place, but mocking needs a document in which
every reference can be followed without touching the filesystem again. Bundling
hoists each referenced fragment into ``components/x-bundled`` and rewrites the
reference to a document-local JSON pointer. Hoisting instead of inlining keeps
recursive schemas finite and makes the result deterministic, because every
(file, fragment) pair is materialized exactly once in walk order.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from ..errors import ExitCode, ToolError
from .model import OpenApiDocument
from .refs import parse_referenced_file, resolve_ref, split_ref

BUNDLE_CONTAINER = "x-bundled"

_MAX_BUNDLED_FRAGMENTS = 500
_UNSAFE_NAME_CHARS = re.compile(r"[^A-Za-z0-9_.-]+")


def bundle_document(
    document: OpenApiDocument, allowed_roots: list[str]
) -> OpenApiDocument:
    """Return ``document`` with all cross-file references hoisted and rewritten.

    Document-local references of the root document are left untouched.
    """
    bundler = _Bundler(document.path, allowed_roots)
    return replace(document, raw=bundler.run(document.raw))


class _Bundler:
    def __init__(self, root_path: str, allowed_roots: list[str]) -> None:
        self._root_path = root_path
        self._allowed_roots = allowed_roots
        self._documents: dict[str, Any] = {}
        self._names: dict[tuple[str, str], str] = {}
        self._fragments: dict[str, Any] = {}

    def run(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        self._documents[self._root_path] = raw
        bundled = self._walk(raw, raw, self._root_path)
        if not isinstance(bundled, dict):
            raise _bundle_error(
                "Bundled OpenAPI document is not a mapping.", self._root_path
            )
        if not self._fragments:
            return bundled
        components = dict(bundled.get("components") or {})
        if BUNDLE_CONTAINER in components:
            raise _bundle_error(
                f"Document already defines components/{BUNDLE_CONTAINER}.",
                self._root_path,
            )
        components[BUNDLE_CONTAINER] = self._fragments
        bundled["components"] = components
        return bundled

    def _walk(self, node: Any, base_document: Any, base_path: str) -> Any:
        if isinstance(node, Mapping):
            ref = node.get("$ref")
            if isinstance(ref, str):
                return self._rewrite_ref(node, ref, base_document, base_path)
            return {
                key: self._walk(value, base_document, base_path)
                for key, value in node.items()
            }
        if isinstance(node, Sequence) and not isinstance(node, (str, bytes)):
            return [self._walk(item, base_document, base_path) for item in node]
        return node

    def _rewrite_ref(
        self,
        node: Mapping[str, Any],
        ref: str,
        base_document: Any,
        base_path: str,
    ) -> dict[str, Any]:
        file_part, fragment = split_ref(ref)
        if file_part == "" and base_path == self._root_path:
            return dict(node)

        resolved = resolve_ref(base_document, base_path, ref, self._allowed_roots)
        target_path = str(resolved.file_path)
        key = (target_path, fragment)
        name = self._names.get(key)
        if name is None:
            name = self._register(key, resolved.value, target_path)
        return {"$ref": f"#/components/{BUNDLE_CONTAINER}/{name}"}

    def _register(self, key: tuple[str, str], value: Any, target_path: str) -> str:
        if len(self._names) >= _MAX_BUNDLED_FRAGMENTS:
            raise _bundle_error(
                f"More than {_MAX_BUNDLED_FRAGMENTS} referenced fragments were bundled.",
                self._root_path,
            )
        name = self._unique_name(key)
        self._names[key] = name
        # Reserve the slot before descending so that recursive references
        # find the name instead of expanding forever.
        self._fragments[name] = None
        target_document = self._document(target_path)
        self._fragments[name] = self._walk(value, target_document, target_path)
        return name

    def _unique_name(self, key: tuple[str, str]) -> str:
        target_path, fragment = key
        pointer = fragment[2:] if fragment.startswith("#/") else fragment.lstrip("#/")
        parts = [
            Path(target_path).stem,
            *(segment for segment in pointer.split("/") if segment),
        ]
        base = _UNSAFE_NAME_CHARS.sub("_", "_".join(parts)) or "fragment"
        candidate = base
        suffix = 2
        while candidate in self._fragments:
            candidate = f"{base}_{suffix}"
            suffix += 1
        return candidate

    def _document(self, path: str) -> Any:
        if path not in self._documents:
            self._documents[path] = parse_referenced_file(
                Path(path), ref=path, file_label=self._root_path
            )
        return self._documents[path]


def _bundle_error(message: str, file_label: str) -> ToolError:
    return ToolError(
        "OPENAPI_REF_BUNDLE_FAILED", message, ExitCode.VALIDATION_ERROR, file_label
    )
