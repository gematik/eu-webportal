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

"""Deterministic, versioned mock package creation and loading."""

from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

import httpx

from ..errors import ExitCode, ToolError
from ..http.execution import HttpResponse
from ..openapi.contracts import validate_response_contract
from ..openapi.model import OpenApiDocument
from .model import MockResponse, MockRoute

PACKAGE_FORMAT_VERSION = "1.0.0"
_SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
_SAFE_FILENAME = re.compile(r"[^A-Za-z0-9_.-]+")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_HEADER_NAME = re.compile(r"^[!#$%&'*+\-.^_`|~A-Za-z0-9]+$")
_MANAGED_HEADERS = frozenset({"connection", "content-length", "transfer-encoding"})
_MAX_PACKAGE_JSON_BYTES = 100 * 1024 * 1024
_MAX_PACKAGE_FILES = 2048
_MAX_PACKAGE_BYTES = 512 * 1024 * 1024


def generator_version() -> str:
    """Return the independently versioned installed generator distribution."""
    try:
        value = version("openapi-arazzo-tool")
    except PackageNotFoundError as error:
        raise ToolError(
            "MOCK_GENERATOR_VERSION_UNAVAILABLE",
            "Install the generator package to create versioned mock packages.",
            ExitCode.CONFIGURATION_ERROR,
        ) from error
    _require_semver(value, "generator")
    return value


def write_mock_package(
    output_directory: str | Path,
    package_version: str,
    generator_semver: str,
    documents: Sequence[OpenApiDocument],
    routes: Sequence[MockRoute],
    openapi_sources: Sequence[str | Path],
    arazzo_sources: Sequence[str | Path],
    *,
    source_references: Sequence[Mapping[str, Any]] = (),
) -> Path:
    """Write a self-contained package directory without overwriting a release."""
    _require_semver(package_version, "package")
    _require_semver(generator_semver, "generator")
    if not documents or not routes:
        raise _package_error(
            "A mock package requires OpenAPI documents and generated routes."
        )
    if not openapi_sources:
        raise _package_error(
            "A mock package must include its source OpenAPI definitions."
        )

    output = Path(output_directory).absolute()
    if output.exists() or output.is_symlink():
        raise _package_error(f"Package output already exists: {output}.")
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    except OSError as error:
        raise ToolError(
            "MOCK_PACKAGE_WRITE_FAILED",
            f"Unable to create package output directory: {error}.",
            ExitCode.CONFIGURATION_ERROR,
            str(output),
        ) from error
    try:
        files: dict[str, str] = {}
        source_manifest = {
            "openapi": _copy_sources(temporary, "openapi", openapi_sources, files),
            "arazzo": _copy_sources(temporary, "arazzo", arazzo_sources, files),
        }
        contracts_directory = temporary / "runtime" / "contracts"
        contracts_directory.mkdir(parents=True)
        document_indexes = {
            id(document.raw): index for index, document in enumerate(documents)
        }
        for index, document in enumerate(documents):
            _write_json(
                temporary,
                f"runtime/contracts/openapi-{index + 1:04d}.json",
                document.raw,
                files,
            )

        runtime_routes = []
        for route in routes:
            document_index = document_indexes.get(id(route.document))
            if document_index is None:
                raise _package_error(
                    "A generated route refers to an unknown OpenAPI document."
                )
            validate_response_contract(
                route.document,
                route.operation,
                HttpResponse(
                    route.response.status_code,
                    httpx.Headers(route.response.headers),
                    route.response.body,
                    "mock://package-export",
                ),
            )
            runtime_routes.append(
                {
                    "method": route.method,
                    "path": route.path_template,
                    "operationId": route.operation_id,
                    "contract": document_index + 1,
                    "response": {
                        "status": route.response.status_code,
                        "headers": dict(route.response.headers),
                        "bodyBase64": base64.b64encode(route.response.body).decode(
                            "ascii"
                        ),
                    },
                    "delayMs": route.delay_seconds * 1000,
                }
            )
        _write_json(temporary, "runtime/routes.json", runtime_routes, files)

        manifest = {
            "formatVersion": PACKAGE_FORMAT_VERSION,
            "packageVersion": package_version,
            "generatorVersion": generator_semver,
            "sources": source_manifest,
            "sourceReferences": list(source_references),
            "files": dict(sorted(files.items())),
        }
        _write_bytes(
            temporary / "manifest.json",
            _json_bytes(manifest),
        )
        load_mock_package(temporary)
        os.replace(temporary, output)
    except OSError as error:
        shutil.rmtree(temporary, ignore_errors=True)
        raise ToolError(
            "MOCK_PACKAGE_WRITE_FAILED",
            f"Unable to write mock package: {error}.",
            ExitCode.CONFIGURATION_ERROR,
            str(output),
        ) from error
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return output


def load_mock_package(
    package_directory: str | Path,
) -> tuple[dict[str, Any], tuple[MockRoute, ...]]:
    """Load and integrity-check runtime data without parsing source definitions."""
    given_path = Path(package_directory)
    if given_path.is_symlink():
        raise _invalid_package("Package directory must not be a symbolic link.")
    try:
        root = given_path.resolve(strict=True)
    except OSError as error:
        raise _invalid_package(
            f"Package directory cannot be resolved: {error}."
        ) from error
    if not root.is_dir():
        raise _invalid_package("Package path must be a directory.")

    manifest = _load_json_file(root, "manifest.json")
    if not isinstance(manifest, dict):
        raise _invalid_package("Package manifest root must be a JSON object.")
    _validate_manifest(manifest)
    contents = _verify_package_files(root, manifest["files"])
    contract_documents = _load_contract_documents(contents)
    routes = _load_runtime_routes(contents, contract_documents)
    return manifest, routes


def _validate_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest.get("formatVersion") != PACKAGE_FORMAT_VERSION:
        raise _invalid_package(
            f"Unsupported package format version: {manifest.get('formatVersion')!r}."
        )
    for key in ("packageVersion", "generatorVersion"):
        value = manifest.get(key)
        if not isinstance(value, str) or not _SEMVER.fullmatch(value):
            raise _invalid_package(f"Manifest field '{key}' is not a semantic version.")
    files = manifest.get("files")
    if not isinstance(files, Mapping) or not files:
        raise _invalid_package("Manifest must list package files and SHA-256 hashes.")
    if len(files) > _MAX_PACKAGE_FILES:
        raise _invalid_package("Package contains too many files.")
    for relative, digest in files.items():
        _safe_package_path(relative)
        if relative == "manifest.json":
            raise _invalid_package(
                "Manifest must not list itself as a package artifact."
            )
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            raise _invalid_package(
                f"Invalid SHA-256 entry for package file {relative!r}."
            )
    sources = manifest.get("sources")
    if not isinstance(sources, Mapping) or not all(
        isinstance(sources.get(kind), list) for kind in ("openapi", "arazzo")
    ):
        raise _invalid_package("Manifest source inventory is invalid.")
    if not sources["openapi"]:
        raise _invalid_package("Package must include source OpenAPI definitions.")
    for kind in ("openapi", "arazzo"):
        for source in sources[kind]:
            if not isinstance(source, Mapping):
                raise _invalid_package(
                    f"Manifest {kind} source entry must be an object."
                )
            relative = source.get("file")
            if (
                not isinstance(relative, str)
                or relative not in files
                or source.get("sha256") != files.get(relative)
                or not isinstance(source.get("name"), str)
                or not relative.startswith(f"sources/{kind}/")
            ):
                raise _invalid_package(
                    f"Manifest {kind} source checksum does not match."
                )
    _validate_source_references(manifest.get("sourceReferences", []), sources)


def _validate_source_references(references: Any, sources: Mapping[str, Any]) -> None:
    if not isinstance(references, list):
        raise _invalid_package("Source references must be an array.")
    for reference in references:
        if (
            not isinstance(reference, Mapping)
            or not isinstance(reference.get("reference"), str)
            or not isinstance(reference.get("location"), str)
        ):
            raise _invalid_package("Source reference metadata is invalid.")
        for endpoint_name in ("source", "target"):
            endpoint = reference.get(endpoint_name)
            if not isinstance(endpoint, Mapping):
                raise _invalid_package("Source reference endpoint must be an object.")
            kind = endpoint.get("kind")
            index = endpoint.get("index")
            if (
                not isinstance(kind, str)
                or kind not in {"openapi", "arazzo"}
                or not isinstance(index, int)
                or isinstance(index, bool)
                or not 1 <= index <= len(sources[kind])
            ):
                raise _invalid_package(
                    "Source reference endpoint is outside the inventory."
                )


def _verify_package_files(root: Path, files: Mapping[str, str]) -> dict[str, bytes]:
    expected = {"manifest.json", *files.keys()}
    actual: set[str] = set()
    for current, directories, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        for directory in directories:
            if (current_path / directory).is_symlink():
                raise _invalid_package("Package must not contain symbolic links.")
        for filename in filenames:
            candidate = current_path / filename
            if candidate.is_symlink() or not candidate.is_file():
                raise _invalid_package("Package entries must be regular files.")
            actual.add(candidate.relative_to(root).as_posix())
    if actual != expected:
        raise _invalid_package("Package files do not match the manifest inventory.")

    total_bytes = 0
    contents = {}
    for relative, expected_hash in files.items():
        path = _resolve_package_file(root, relative)
        try:
            size = path.stat().st_size
        except OSError as error:
            raise _invalid_package(
                f"Package file {relative} cannot be read."
            ) from error
        total_bytes += size
        if size > _MAX_PACKAGE_JSON_BYTES or total_bytes > _MAX_PACKAGE_BYTES:
            raise _invalid_package("Package exceeds the supported size limit.")
        content = _read_package_bytes(path, relative)
        if _sha256(content) != expected_hash:
            raise _invalid_package(f"SHA-256 verification failed for {relative}.")
        contents[relative] = content
    return contents


def _load_contract_documents(
    contents: Mapping[str, bytes],
) -> dict[int, Mapping[str, Any]]:
    documents: dict[int, Mapping[str, Any]] = {}
    for relative, content in contents.items():
        match = re.fullmatch(r"runtime/contracts/openapi-(\d{4})\.json", relative)
        if not match:
            continue
        value = _decode_json(content, relative)
        if not isinstance(value, Mapping) or not isinstance(
            value.get("paths"), Mapping
        ):
            raise _invalid_package(f"Runtime contract document {relative} is invalid.")
        documents[int(match.group(1))] = value
    if not documents or sorted(documents) != list(range(1, len(documents) + 1)):
        raise _invalid_package("Runtime OpenAPI contract documents are incomplete.")
    return documents


def _load_runtime_routes(
    contents: Mapping[str, bytes],
    documents: Mapping[int, Mapping[str, Any]],
) -> tuple[MockRoute, ...]:
    route_content = contents.get("runtime/routes.json")
    if route_content is None:
        raise _invalid_package("Package has no runtime route data.")
    raw_routes = _decode_json(route_content, "runtime/routes.json")
    if not isinstance(raw_routes, list) or not raw_routes:
        raise _invalid_package("Runtime routes must be a non-empty JSON array.")
    routes = []
    seen: set[tuple[str, str]] = set()
    for index, raw in enumerate(raw_routes):
        if not isinstance(raw, Mapping):
            raise _invalid_package(f"Runtime route {index} must be a JSON object.")
        method = raw.get("method")
        path = raw.get("path")
        operation_id = raw.get("operationId")
        contract = raw.get("contract")
        if (
            not isinstance(method, str)
            or method
            not in {"DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"}
            or not isinstance(path, str)
            or not path.startswith("/")
            or not isinstance(operation_id, str)
            or not operation_id
            or not isinstance(contract, int)
            or isinstance(contract, bool)
            or contract not in documents
        ):
            raise _invalid_package(
                f"Runtime route {index} has invalid identity or contract."
            )
        key = (method, path)
        if key in seen:
            raise _invalid_package(
                f"Runtime package contains duplicate route {method} {path}."
            )
        seen.add(key)
        document = documents[contract]
        path_item = document["paths"].get(path)
        operation = (
            path_item.get(method.lower()) if isinstance(path_item, Mapping) else None
        )
        if not isinstance(path_item, Mapping) or not isinstance(operation, Mapping):
            raise _invalid_package(
                f"Runtime route {method} {path} has no matching contract."
            )
        if operation.get("operationId") != operation_id:
            raise _invalid_package(
                f"Runtime route {method} {path} has a mismatched operationId."
            )
        response = raw.get("response")
        if not isinstance(response, Mapping):
            raise _invalid_package(f"Runtime route {method} {path} has no response.")
        status = response.get("status")
        headers = response.get("headers")
        body = response.get("bodyBase64")
        delay_ms = raw.get("delayMs")
        if (
            not isinstance(status, int)
            or isinstance(status, bool)
            or not 100 <= status <= 599
            or not isinstance(headers, Mapping)
            or not _valid_runtime_headers(headers)
            or not isinstance(body, str)
            or not isinstance(delay_ms, (int, float))
            or isinstance(delay_ms, bool)
            or not math.isfinite(delay_ms)
            or delay_ms < 0
        ):
            raise _invalid_package(
                f"Runtime route {method} {path} response metadata is invalid."
            )
        try:
            response_body = base64.b64decode(body, validate=True)
        except ValueError as error:
            raise _invalid_package(
                f"Runtime route {method} {path} body is invalid base64."
            ) from error
        try:
            routes.append(
                MockRoute(
                    method,
                    path,
                    operation_id,
                    document,
                    path_item,
                    operation,
                    MockResponse(status, dict(headers), response_body),
                    delay_ms / 1000,
                )
            )
        except (TypeError, ValueError, re.error) as error:
            raise _invalid_package(
                f"Runtime route {method} {path} cannot be constructed."
            ) from error
    return tuple(routes)


def _valid_runtime_headers(headers: Mapping[Any, Any]) -> bool:
    normalized_names = set()
    for name, value in headers.items():
        if (
            not isinstance(name, str)
            or not _HEADER_NAME.fullmatch(name)
            or name.lower() in _MANAGED_HEADERS
            or name.lower() in normalized_names
            or not isinstance(value, str)
            or "\r" in value
            or "\n" in value
        ):
            return False
        normalized_names.add(name.lower())
    return True


def _load_json_file(root: Path, relative: str) -> Any:
    path = _resolve_package_file(root, relative)
    try:
        size = path.stat().st_size
    except OSError as error:
        raise _invalid_package(f"Package file {relative} cannot be read.") from error
    if size > _MAX_PACKAGE_JSON_BYTES:
        raise _invalid_package(
            f"Package file {relative} exceeds the supported size limit."
        )
    return _decode_json(_read_package_bytes(path, relative), relative)


def _read_package_bytes(path: Path, relative: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise _invalid_package(f"Package file {relative} cannot be read.") from error


def _decode_json(content: bytes, label: str) -> Any:
    try:
        return json.loads(content, object_pairs_hook=_unique_object)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        RecursionError,
    ) as error:
        raise _invalid_package(
            f"Package file {label} is not valid unambiguous JSON."
        ) from error


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON object member: {key}.")
        result[key] = value
    return result


def _safe_package_path(relative: Any) -> str:
    if not isinstance(relative, str) or "\\" in relative or ":" in relative:
        raise _invalid_package("Package file paths must be relative POSIX paths.")
    if (
        not relative
        or relative.startswith("/")
        or any(part in {"", ".", ".."} for part in relative.split("/"))
    ):
        raise _invalid_package("Package file path escapes the package directory.")
    return relative


def _resolve_package_file(root: Path, relative: str) -> Path:
    safe = _safe_package_path(relative)
    path = root.joinpath(*safe.split("/"))
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise _invalid_package(f"Package file {relative} is missing.") from error
    if not resolved.is_relative_to(root) or path.is_symlink() or not resolved.is_file():
        raise _invalid_package(
            f"Package file {relative} is not a regular in-package file."
        )
    return resolved


def _copy_sources(
    package_root: Path,
    kind: str,
    sources: Sequence[str | Path],
    files: dict[str, str],
) -> list[dict[str, str]]:
    records = []
    for index, source in enumerate(sources, start=1):
        path = Path(source)
        try:
            content = path.read_bytes()
        except OSError as error:
            raise ToolError(
                "MOCK_PACKAGE_SOURCE_UNREADABLE",
                f"Unable to include {kind} source: {error}.",
                ExitCode.VALIDATION_ERROR,
                str(path),
            ) from error
        safe_name = _SAFE_FILENAME.sub("_", path.name) or f"{kind}.yaml"
        relative = f"sources/{kind}/{index:04d}-{safe_name}"
        _write_bytes(package_root / relative, content)
        files[relative] = _sha256(content)
        records.append(
            {
                "file": relative,
                "name": path.name,
                "sha256": files[relative],
            }
        )
    return records


def _write_json(
    package_root: Path,
    relative: str,
    value: Any,
    files: dict[str, str],
) -> None:
    content = _json_bytes(value)
    _write_bytes(package_root / relative, content)
    files[relative] = _sha256(content)


def _write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _json_bytes(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise _package_error(
            "A generated package artifact is not JSON-serializable."
        ) from error


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _require_semver(value: str, label: str) -> None:
    if not isinstance(value, str) or not _SEMVER.fullmatch(value):
        raise _package_error(f"The {label} version must follow semantic versioning.")


def _invalid_package(message: str) -> ToolError:
    return ToolError(
        "MOCK_PACKAGE_INVALID",
        message,
        ExitCode.VALIDATION_ERROR,
    )


def _package_error(message: str) -> ToolError:
    return ToolError(
        "MOCK_PACKAGE_INVALID",
        message,
        ExitCode.CONFIGURATION_ERROR,
    )
