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

"""Deterministic HTTP request assembly from serialized OpenAPI values."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from ..errors import ExitCode, ToolError
from .bodies import serialize_request_body
from .parameters import serialize_parameters

_HTTP_METHODS = frozenset(
    {"DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT", "TRACE"}
)
_TOKEN = re.compile(r"^[!#$%&'*+\-.^_`|~A-Za-z0-9]+$")


@dataclass(frozen=True)
class HttpRequest:
    """Transport-neutral HTTP request produced by Milestone 5."""

    method: str
    url: str
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes | None = None


def build_http_request(
    method: str,
    base_url: str,
    path_template: str,
    parameters: Sequence[Mapping[str, Any]],
    parameter_values: Mapping[tuple[str, str], Any],
    *,
    headers: Mapping[str, str] | None = None,
    body_payload: Any = None,
    body_content_type: str | None = None,
    body_encoding: Mapping[str, Mapping[str, Any]] | None = None,
    multipart_boundary: str | None = None,
) -> HttpRequest:
    """Assemble a request without performing target or network access."""
    normalized_method = method.upper()
    if normalized_method not in _HTTP_METHODS:
        raise _request_error(f"Unsupported HTTP method '{method}'.")
    base = urlsplit(base_url)
    if base.scheme not in {"http", "https"} or not base.netloc:
        raise _request_error("Base URL must be an absolute HTTP or HTTPS URL.")
    if base.query or base.fragment:
        raise _request_error("Base URL must not contain query or fragment components.")

    serialized = serialize_parameters(path_template, parameters, parameter_values)
    path = _join_paths(base.path, serialized.path)
    query = "&".join(f"{name}={value}" for name, value in serialized.query)
    url = urlunsplit((base.scheme, base.netloc, path, query, ""))

    final_headers = _validate_headers(headers or {})
    _merge_headers(final_headers, serialized.headers)
    if serialized.cookies:
        if _contains_header(final_headers, "Cookie"):
            raise _request_error(
                "Cookie header conflicts with serialized cookie parameters."
            )
        for name in serialized.cookies:
            if not _TOKEN.fullmatch(name):
                raise _request_error(f"Cookie name '{name}' is invalid.")
        final_headers["Cookie"] = "; ".join(
            f"{name}={value}" for name, value in serialized.cookies.items()
        )

    body: bytes | None = None
    if body_content_type is not None:
        serialized_body = serialize_request_body(
            body_payload,
            body_content_type,
            body_encoding,
            multipart_boundary=multipart_boundary,
        )
        if _contains_header(final_headers, "Content-Type"):
            raise _request_error(
                "Content-Type header conflicts with serialized request body."
            )
        final_headers["Content-Type"] = serialized_body.content_type
        body = serialized_body.data
    elif body_payload is not None:
        raise _request_error("Request body payload requires a content type.")

    return HttpRequest(normalized_method, url, final_headers, body)


def _join_paths(base_path: str, operation_path: str) -> str:
    base = base_path.rstrip("/")
    operation = (
        operation_path if operation_path.startswith("/") else f"/{operation_path}"
    )
    return f"{base}{operation}" or "/"


def _validate_headers(headers: Mapping[str, str]) -> dict[str, str]:
    validated: dict[str, str] = {}
    for name, value in headers.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise _request_error("HTTP header names and values must be strings.")
        if not _TOKEN.fullmatch(name):
            raise _request_error(f"HTTP header name '{name}' is invalid.")
        if "\r" in value or "\n" in value:
            raise _request_error(f"HTTP header '{name}' contains forbidden CR or LF.")
        if _contains_header(validated, name):
            raise _request_error(f"Duplicate HTTP header '{name}'.")
        validated[name] = value
    return validated


def _merge_headers(target: dict[str, str], additions: Mapping[str, str]) -> None:
    for name, value in additions.items():
        if not _TOKEN.fullmatch(name):
            raise _request_error(f"HTTP header name '{name}' is invalid.")
        if _contains_header(target, name):
            raise _request_error(f"HTTP header '{name}' is supplied more than once.")
        if "\r" in value or "\n" in value:
            raise _request_error(f"HTTP header '{name}' contains forbidden CR or LF.")
        target[name] = value


def _contains_header(headers: Mapping[str, str], name: str) -> bool:
    normalized = name.lower()
    return any(header.lower() == normalized for header in headers)


def _request_error(message: str) -> ToolError:
    return ToolError(
        "HTTP_REQUEST_CONSTRUCTION_FAILED",
        message,
        ExitCode.TEST_ERROR,
    )
