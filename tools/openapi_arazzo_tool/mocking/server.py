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

"""Local stateless HTTP server for generated OpenAPI mocks."""

from __future__ import annotations

import json
import time
from collections.abc import Mapping
from email.message import Message
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from ..errors import ToolError
from ..http.requests import HttpRequest
from ..openapi.contracts import effective_runtime_parameters, validate_request_contract
from .model import MockRoute


class MockHttpServer(ThreadingHTTPServer):
    """Threaded server carrying immutable generated routes."""

    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        routes: tuple[MockRoute, ...],
        *,
        validate_requests: bool = True,
        max_request_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        self.routes = routes
        self.validate_requests = validate_requests
        self.max_request_bytes = max_request_bytes
        super().__init__(address, MockRequestHandler)


class MockRequestHandler(BaseHTTPRequestHandler):
    """Serve deterministic responses without shared scenario state."""

    server: MockHttpServer

    def do_DELETE(self) -> None:
        self._handle()

    def do_GET(self) -> None:
        self._handle()

    def do_HEAD(self) -> None:
        self._handle()

    def do_OPTIONS(self) -> None:
        self._handle()

    def do_PATCH(self) -> None:
        self._handle()

    def do_POST(self) -> None:
        self._handle()

    def do_PUT(self) -> None:
        self._handle()

    def do_TRACE(self) -> None:
        self._handle()

    def _handle(self) -> None:
        parsed = urlsplit(self.path)
        route, path_values = self._find_route(parsed.path)
        if route is None:
            self._json_error(
                404, "MOCK_ROUTE_NOT_FOUND", "No mock route matches this request."
            )
            return
        try:
            body = self._read_body()
            if self.server.validate_requests:
                values = _request_values(route, path_values, parsed.query, self.headers)
                content_type = self.headers.get("Content-Type")
                payload = _decode_request_body(body, content_type)
                validate_request_contract(
                    route.document,
                    route.path_item,
                    route.operation,
                    values,
                    HttpRequest(
                        self.command, self.path, dict(self.headers), body or None
                    ),
                    payload,
                    content_type,
                )
        except ToolError as error:
            self._json_error(400, error.code, error.message)
            return
        except ValueError as error:
            self._json_error(400, "MOCK_REQUEST_INVALID", str(error))
            return

        if route.delay_seconds:
            time.sleep(route.delay_seconds)
        self.send_response(route.response.status_code)
        for name, value in route.response.headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(route.response.body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(route.response.body)

    def _find_route(self, path: str) -> tuple[MockRoute | None, dict[str, str]]:
        for route in self.server.routes:
            if route.method != self.command:
                continue
            match = route.path_pattern.fullmatch(path)
            if match:
                return route, {
                    name: unquote(value) for name, value in match.groupdict().items()
                }
        return None, {}

    def _read_body(self) -> bytes:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as error:
            raise ValueError("Content-Length must be an integer.") from error
        if length < 0 or length > self.server.max_request_bytes:
            raise ValueError("Request body exceeds configured size limit.")
        return self.rfile.read(length)

    def _json_error(self, status: int, code: str, message: str) -> None:
        body = json.dumps(
            {"code": code, "message": message},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


def create_mock_server(
    bind_host: str,
    port: int,
    routes: tuple[MockRoute, ...],
    *,
    validate_requests: bool = True,
    max_request_bytes: int = 10 * 1024 * 1024,
) -> MockHttpServer:
    """Create but do not start a configured local mock server."""
    if not bind_host:
        raise ValueError("Mock bind host must be configured.")
    if not 0 <= port <= 65535:
        raise ValueError("Mock port must be between 0 and 65535.")
    if max_request_bytes <= 0:
        raise ValueError("Maximum request size must be positive.")
    return MockHttpServer(
        (bind_host, port),
        routes,
        validate_requests=validate_requests,
        max_request_bytes=max_request_bytes,
    )


def _request_values(
    route: MockRoute,
    path_values: Mapping[str, str],
    raw_query: str,
    headers: Mapping[str, str] | Message[str, str],
) -> dict[tuple[str, str], Any]:
    query = parse_qs(raw_query, keep_blank_values=True)
    cookies = SimpleCookie()
    cookies.load(headers.get("Cookie", ""))
    values: dict[tuple[str, str], Any] = {}
    for parameter in effective_runtime_parameters(
        route.document,
        route.path_item,
        route.operation,
    ).values():
        name = parameter["name"]
        location = parameter["in"]
        raw: Any = None
        if location == "path":
            raw = path_values.get(name)
        elif location == "query":
            found = query.get(name)
            raw = (
                found
                if _schema_type(parameter) == "array"
                else found[0]
                if found
                else None
            )
        elif location == "header":
            raw = headers.get(name)
        elif location == "cookie" and name in cookies:
            raw = cookies[name].value
        if raw is not None:
            values[(name, location)] = _coerce(raw, parameter.get("schema"))
    return values


def _schema_type(parameter: Mapping[str, Any]) -> Any:
    schema = parameter.get("schema")
    return schema.get("type") if isinstance(schema, Mapping) else None


def _coerce(value: Any, schema: Any) -> Any:
    if not isinstance(schema, Mapping):
        return value
    schema_type = schema.get("type")
    if schema_type == "array":
        values = value if isinstance(value, list) else str(value).split(",")
        return [_coerce(item, schema.get("items")) for item in values]
    if schema_type == "integer":
        return int(value)
    if schema_type == "number":
        return float(value)
    if schema_type == "boolean":
        normalized = str(value).lower()
        if normalized not in {"true", "false"}:
            raise ValueError(f"Boolean parameter value '{value}' is invalid.")
        return normalized == "true"
    return value


def _decode_request_body(body: bytes, content_type: str | None) -> Any:
    if not body:
        return None
    normalized = (content_type or "").partition(";")[0].strip().lower()
    if normalized == "application/json" or normalized.endswith("+json"):
        try:
            return json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Request body is not valid JSON.") from error
    if normalized.startswith("text/") or normalized in {
        "application/xml",
        "application/xhtml+xml",
    }:
        try:
            return body.decode()
        except UnicodeDecodeError as error:
            raise ValueError("Request body is not valid UTF-8 text.") from error
    return body
