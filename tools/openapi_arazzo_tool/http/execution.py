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

"""Controlled HTTP execution with SSRF and response-size protections."""

import ipaddress
import socket
import ssl
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpcore
import httpx

from ..errors import ExitCode, ToolError
from .requests import HttpRequest


@dataclass(frozen=True)
class NetworkPolicy:
    """Explicit network boundary for workflow HTTP execution."""

    allowed_hosts: frozenset[str]
    allowed_ports: frozenset[int]
    allow_private_addresses: bool = False
    request_timeout_seconds: float = 5.0
    redirect_limit: int = 3
    max_response_bytes: int = 10 * 1024 * 1024


@dataclass(frozen=True)
class HttpResponse:
    """Bounded HTTP response returned to the workflow runner."""

    status_code: int
    headers: httpx.Headers
    body: bytes
    url: str


Resolver = Callable[[str, int], Iterable[str]]
SocketOption = (
    tuple[int, int, int]
    | tuple[int, int, bytes | bytearray]
    | tuple[int, int, None, int]
)


def execute_http_request(
    request: HttpRequest,
    policy: NetworkPolicy,
    *,
    transport: httpx.BaseTransport | None = None,
    resolver: Resolver | None = None,
) -> HttpResponse:
    """Execute a request while revalidating every redirect target."""
    if (
        policy.request_timeout_seconds <= 0
        or policy.redirect_limit < 0
        or policy.max_response_bytes <= 0
    ):
        raise _network_error(
            "Network limits must be positive and redirect limit non-negative."
        )
    current = request
    resolve = resolver or _resolve_addresses
    effective_transport = transport or _PinnedHTTPTransport(policy, resolve)
    with httpx.Client(
        transport=effective_transport,
        timeout=policy.request_timeout_seconds,
        follow_redirects=False,
        trust_env=False,
    ) as client:
        for redirect_count in range(policy.redirect_limit + 1):
            _validate_target(current.url, policy, resolve)
            try:
                with client.stream(
                    current.method,
                    current.url,
                    headers=current.headers,
                    content=current.body,
                ) as response:
                    response_body = _read_bounded(
                        response.iter_bytes(), policy.max_response_bytes
                    )
                    result = HttpResponse(
                        response.status_code,
                        response.headers,
                        response_body,
                        str(response.url),
                    )
            except httpx.TimeoutException as error:
                raise _network_error("HTTP request timed out.") from error
            except httpx.HTTPError as error:
                raise _network_error(f"HTTP request failed: {error}") from error

            location = result.headers.get("location")
            if result.status_code not in {301, 302, 303, 307, 308} or not location:
                return result
            if redirect_count >= policy.redirect_limit:
                raise _network_error("HTTP redirect limit exceeded.")
            redirect_url = urljoin(current.url, location)
            method, body = _redirect_request(
                current.method, current.body, result.status_code
            )
            headers = _redirect_headers(current, redirect_url, method)
            current = HttpRequest(method, redirect_url, headers, body)
    raise _network_error("HTTP execution terminated unexpectedly.")


def _validate_target(url: str, policy: NetworkPolicy, resolver: Resolver) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise _network_error("Request target must be an absolute HTTP or HTTPS URL.")
    host = parsed.hostname.lower()
    if host not in {allowed.lower() for allowed in policy.allowed_hosts}:
        raise _network_error(f"Target host '{host}' is not allowed.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in policy.allowed_ports:
        raise _network_error(f"Target port '{port}' is not allowed.")
    _validated_addresses(host, port, policy, resolver)


def _validated_addresses(
    host: str,
    port: int,
    policy: NetworkPolicy,
    resolver: Resolver,
) -> tuple[str, ...]:
    addresses = sorted(set(resolver(host, port)))
    if not addresses:
        raise _network_error(f"Target host '{host}' did not resolve.")
    for address in addresses:
        try:
            parsed_address = ipaddress.ip_address(address)
        except ValueError as error:
            raise _network_error(
                f"Resolved target address '{address}' is invalid."
            ) from error
        if (
            parsed_address.is_multicast
            or parsed_address.is_unspecified
            or parsed_address.is_reserved
        ):
            raise _network_error(f"Resolved target address '{address}' is forbidden.")
        if not policy.allow_private_addresses and not parsed_address.is_global:
            raise _network_error(
                f"Resolved target address '{address}' is not publicly routable."
            )
    return tuple(addresses)


def _resolve_addresses(host: str, port: int) -> set[str]:
    try:
        addresses: set[str] = set()
        for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM):
            address = item[4][0]
            if isinstance(address, str):
                addresses.add(address)
        return addresses
    except socket.gaierror as error:
        raise _network_error(f"Target host '{host}' cannot be resolved.") from error


def _read_bounded(chunks: Iterable[bytes], limit: int) -> bytes:
    body = bytearray()
    for chunk in chunks:
        if len(body) + len(chunk) > limit:
            raise _network_error("HTTP response exceeds configured size limit.")
        body.extend(chunk)
    return bytes(body)


def _redirect_request(
    method: str, body: bytes | None, status: int
) -> tuple[str, bytes | None]:
    if status == 303 or (status in {301, 302} and method == "POST"):
        return "GET", None
    return method, body


def _redirect_headers(
    request: HttpRequest,
    redirect_url: str,
    method: str,
) -> dict[str, str]:
    headers = dict(request.headers)
    if _origin(request.url) != _origin(redirect_url):
        blocked = {"authorization", "cookie", "proxy-authorization"}
        headers = {
            name: value
            for name, value in headers.items()
            if name.lower() not in blocked
        }
    if method == "GET" and request.method != "GET":
        blocked = {"content-length", "content-type", "transfer-encoding"}
        headers = {
            name: value
            for name, value in headers.items()
            if name.lower() not in blocked
        }
    return headers


def _origin(url: str) -> tuple[str, str | None, int]:
    parsed = urlsplit(url)
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return parsed.scheme, parsed.hostname, port


class _PinnedNetworkBackend(httpcore.SyncBackend):
    def __init__(self, policy: NetworkPolicy, resolver: Resolver) -> None:
        self._policy = policy
        self._resolver = resolver

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[SocketOption] | None = None,
    ) -> httpcore.NetworkStream:
        address = _validated_addresses(host, port, self._policy, self._resolver)[0]
        return super().connect_tcp(
            address, port, timeout, local_address, socket_options
        )


class _PinnedHTTPTransport(httpx.HTTPTransport):
    def __init__(self, policy: NetworkPolicy, resolver: Resolver) -> None:
        self._pool = httpcore.ConnectionPool(
            ssl_context=ssl.create_default_context(),
            network_backend=_PinnedNetworkBackend(policy, resolver),
        )


def _network_error(message: str) -> ToolError:
    return ToolError("HTTP_EXECUTION_FORBIDDEN", message, ExitCode.TEST_ERROR)
