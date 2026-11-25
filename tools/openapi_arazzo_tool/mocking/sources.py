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

"""Collect only the local definition graph needed by a mock package."""

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..arazzo.loader import load_arazzo_document
from ..cross_validation.sources import resolve_sources
from ..openapi.loader import load_openapi_document
from ..openapi.refs import parse_referenced_file, resolve_ref


@dataclass(frozen=True)
class SourceReference:
    """Portable relationship between entries in the ordered source inventories."""

    source_kind: str
    source_index: int
    target_kind: str
    target_index: int
    reference: str
    location: str

    def provenance(self) -> dict[str, Any]:
        """Return provenance without exposing machine-specific absolute paths."""
        return {
            "source": {"kind": self.source_kind, "index": self.source_index},
            "target": {"kind": self.target_kind, "index": self.target_index},
            "reference": self.reference,
            "location": self.location,
        }


@dataclass(frozen=True)
class PackageSources:
    """Ordered source paths and their portable, one-based reference inventory."""

    openapi: tuple[Path, ...]
    arazzo: tuple[Path, ...]
    references: tuple[SourceReference, ...]

    def provenance(self) -> list[dict[str, Any]]:
        """Return serializable relationships matching package source copy order."""
        return [reference.provenance() for reference in self.references]


def collect_package_sources(
    openapi_paths: Sequence[str | Path],
    arazzo_paths: Sequence[str | Path],
    allowed_roots: list[str],
) -> PackageSources:
    """Collect configured roots, reachable local refs, and Arazzo OpenAPI sources.

    Configured roots remain first, in configuration order. Dependencies follow
    deterministic reference traversal order. Files are never rewritten or
    enumerated from directories; the package writer copies their original bytes.
    Only referenced fragments are traversed, matching reference validation.
    """
    collector = _SourceCollector(openapi_paths, arazzo_paths, allowed_roots)
    return collector.collect()


class _SourceCollector:
    def __init__(
        self,
        openapi_paths: Sequence[str | Path],
        arazzo_paths: Sequence[str | Path],
        allowed_roots: list[str],
    ) -> None:
        self._paths = {
            "openapi": list(
                dict.fromkeys(Path(path).resolve() for path in openapi_paths)
            ),
            "arazzo": list(
                dict.fromkeys(Path(path).resolve() for path in arazzo_paths)
            ),
        }
        self._allowed_roots = allowed_roots
        self._documents: dict[Path, Any] = {}
        self._visited: set[tuple[Path, str]] = set()
        self._references: dict[SourceReference, None] = {}

    def collect(self) -> PackageSources:
        for path in tuple(self._paths["openapi"]):
            document = load_openapi_document(str(path))
            self._walk_document(path, document.raw)
        for path in self._paths["arazzo"]:
            self._collect_arazzo(path)
        return PackageSources(
            tuple(self._paths["openapi"]),
            tuple(self._paths["arazzo"]),
            tuple(self._references),
        )

    def _collect_arazzo(self, path: Path) -> None:
        document = load_arazzo_document(str(path))
        sources = resolve_sources(document, self._allowed_roots)
        if sources.issues:
            raise sources.issues[0]
        if not sources.sources:
            return
        for index, source in enumerate(document.raw.get("sourceDescriptions", [])):
            if not isinstance(source, Mapping):
                continue
            name = source.get("name")
            loaded = sources.sources.get(name) if isinstance(name, str) else None
            if loaded is None:
                continue
            target = Path(loaded.path).resolve()
            self._register(target)
            self._add_reference(
                "arazzo",
                path,
                target,
                source["url"],
                f"/sourceDescriptions/{index}/url",
            )
            self._walk_document(target, loaded.raw)

    def _walk_document(self, path: Path, raw: Any) -> None:
        self._documents[path] = raw
        self._walk_target(path, "", raw)

    def _walk_target(self, path: Path, fragment: str, value: Any) -> None:
        key = (path, fragment)
        if key in self._visited:
            return
        self._visited.add(key)
        location = fragment.removeprefix("#")
        for ref, pointer in _references(value, location):
            resolved = resolve_ref(
                self._documents[path], str(path), ref, self._allowed_roots
            )
            target = resolved.file_path.resolve()
            self._register(target)
            self._add_reference("openapi", path, target, ref, pointer)
            if target not in self._documents:
                self._documents[target] = parse_referenced_file(
                    target, ref=ref, file_label=str(path)
                )
            self._walk_target(target, resolved.fragment, resolved.value)

    def _register(self, path: Path) -> None:
        if path not in self._paths["openapi"]:
            self._paths["openapi"].append(path)

    def _add_reference(
        self, kind: str, path: Path, target: Path, ref: str, location: str
    ) -> None:
        reference = SourceReference(
            kind,
            self._paths[kind].index(path) + 1,
            "openapi",
            self._paths["openapi"].index(target) + 1,
            ref,
            location,
        )
        self._references[reference] = None


def _references(node: Any, location: str) -> Iterator[tuple[str, str]]:
    if isinstance(node, Mapping):
        for key, value in node.items():
            pointer = f"{location}/{str(key).replace('~', '~0').replace('/', '~1')}"
            if key == "$ref" and isinstance(value, str):
                yield value, pointer
            else:
                yield from _references(value, pointer)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _references(value, f"{location}/{index}")
