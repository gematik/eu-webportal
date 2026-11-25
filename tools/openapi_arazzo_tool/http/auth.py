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

"""Trust-scoped OpenAPI credentials and output redaction."""

import base64
import os
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import parse_qsl, quote, urlsplit, urlunsplit

from ..errors import ExitCode, ToolError
from .requests import HttpRequest


def authorize_request(
    request: HttpRequest,
    document: Mapping[str, Any],
    operation: Mapping[str, Any],
    workflow_id: str,
    path_template: str,
    auth: Mapping[str, Any] | None,
    *,
    trusted: bool,
    workflow_sha256: str | None = None,
) -> tuple[HttpRequest, tuple[str, ...]]:
    """Choose the first satisfiable OR alternative; require every AND credential."""
    requirements = operation.get("security", document.get("security", []))
    if not requirements:
        return request, ()
    if not isinstance(requirements, list):
        raise _auth_error("OpenAPI security requirements are invalid.")
    schemes = document.get("components", {}).get("securitySchemes", {})
    configured = auth.get("schemes", {}) if isinstance(auth, Mapping) else {}
    if not isinstance(configured, Mapping) or not isinstance(schemes, Mapping):
        raise _auth_error("auth.schemes and OpenAPI securitySchemes must be mappings.")
    failures: list[str] = []
    for requirement in requirements:
        if not isinstance(requirement, Mapping):
            raise _auth_error("OpenAPI security requirement must be a mapping.")
        if not requirement:
            return request, ()
        if not trusted:
            continue
        bindings = {
            name: configured.get(name, _type_binding(auth, schemes.get(name)))
            for name in requirement
        }
        if any(binding is None for binding in bindings.values()):
            continue
        candidate = request
        secrets: list[str] = []
        try:
            for name in requirement:
                candidate, values = _apply_scheme(
                    candidate,
                    name,
                    schemes.get(name),
                    bindings[name],
                    workflow_id,
                    path_template,
                    workflow_sha256,
                )
                secrets.extend(values)
        except ToolError as error:
            failures.append(error.message)
            continue
        return candidate, tuple(secrets)
    if failures:
        raise _auth_error("; ".join(failures))
    raise _auth_error(
        "No authorized credential set satisfies the OpenAPI security requirements."
    )


def _type_binding(auth: Any, scheme: Any) -> Any:
    if not isinstance(auth, Mapping) or not isinstance(scheme, Mapping):
        return None
    if scheme.get("type") == "apiKey":
        return auth.get("apiKey")
    if scheme.get("type") == "http":
        return auth.get(
            {"bearer": "bearerToken", "basic": "basic"}.get(
                str(scheme.get("scheme", "")).lower(), ""
            )
        )
    return None


def _apply_scheme(
    request: HttpRequest,
    name: str,
    scheme: Any,
    binding: Any,
    workflow_id: str,
    path_template: str,
    workflow_sha256: str | None,
) -> tuple[HttpRequest, tuple[str, ...]]:
    if not isinstance(scheme, Mapping) or not isinstance(binding, Mapping):
        raise _auth_error(f"Credential binding for scheme '{name}' is invalid.")
    url = urlsplit(request.url)
    origin = f"{url.scheme}://{url.hostname}"
    if url.port is not None:
        origin += f":{url.port}"
    if not (
        workflow_sha256 is not None
        and binding.get("workflowSha256") == workflow_sha256
        and _contains(binding, "workflowIds", workflow_id)
        and _contains(binding, "origins", origin)
        and _contains(binding, "methods", request.method)
        and _contains(binding, "paths", path_template)
    ):
        raise _auth_error(
            f"Credential binding for scheme '{name}' does not permit this request."
        )
    env_name = binding.get("env")
    if not isinstance(env_name, str) or not env_name:
        raise _auth_error(f"Scheme '{name}' must reference an environment variable.")
    value = os.environ.get(env_name)
    if not value:
        raise _auth_error(
            f"Credential for scheme '{name}' is missing from environment."
        )
    if "\r" in value or "\n" in value:
        raise _auth_error(
            f"Credential for scheme '{name}' contains invalid characters."
        )
    if scheme.get("type") == "http" and scheme.get("scheme", "").lower() == "bearer":
        return _header(request, "Authorization", f"Bearer {value}"), (value,)
    if scheme.get("type") == "http" and scheme.get("scheme", "").lower() == "basic":
        username = binding.get("username")
        if (
            not isinstance(username, str)
            or ":" in username
            or "\r" in username
            or "\n" in username
        ):
            raise _auth_error(f"Basic scheme '{name}' requires a valid username.")
        encoded = base64.b64encode(f"{username}:{value}".encode()).decode()
        return _header(request, "Authorization", f"Basic {encoded}"), (value, encoded)
    if scheme.get("type") == "apiKey":
        location = scheme.get("in")
        key = scheme.get("name")
        if not isinstance(key, str):
            raise _auth_error(f"API key scheme '{name}' has no name.")
        if location == "header":
            return _header(request, key, value), (value,)
        if location == "cookie":
            headers = dict(request.headers)
            cookie = next((name for name in headers if name.lower() == "cookie"), None)
            existing = headers.pop(cookie) if cookie else ""
            if any(
                part.strip().partition("=")[0] == key for part in existing.split(";")
            ):
                raise _auth_error(f"Cookie '{key}' conflicts with the credential.")
            headers["Cookie"] = (
                f"{existing}; {key}={quote(value, safe='')}"
                if existing
                else f"{key}={quote(value, safe='')}"
            )
            return HttpRequest(request.method, request.url, headers, request.body), (
                value,
                quote(value, safe=""),
            )
        if location == "query":
            if any(
                param == key
                for param, _ in parse_qsl(url.query, keep_blank_values=True)
            ):
                raise _auth_error(
                    f"Query parameter '{key}' conflicts with the credential."
                )
            suffix = f"{quote(key, safe='')}={quote(value, safe='')}"
            query = f"{url.query}&{suffix}" if url.query else suffix
            return HttpRequest(
                request.method,
                urlunsplit((url.scheme, url.netloc, url.path, query, url.fragment)),
                request.headers,
                request.body,
            ), (value, quote(value, safe=""))
    raise _auth_error(f"Scheme '{name}' cannot be represented by V1 credentials.")


def _header(request: HttpRequest, name: str, value: str) -> HttpRequest:
    if any(key.lower() == name.lower() for key in request.headers):
        raise _auth_error(f"Header '{name}' conflicts with the credential.")
    return HttpRequest(
        request.method, request.url, {**request.headers, name: value}, request.body
    )


def _contains(binding: Mapping[str, Any], key: str, value: str) -> bool:
    values = binding.get(key)
    return (
        isinstance(values, Sequence) and not isinstance(values, str) and value in values
    )


def redact(value: Any, secrets: Sequence[str]) -> Any:
    """Mask secret substrings recursively without mutating input values."""
    if isinstance(value, str):
        for secret in sorted((item for item in secrets if item), key=len, reverse=True):
            value = value.replace(secret, "[REDACTED]")
        return value
    if isinstance(value, Mapping):
        return {key: redact(item, secrets) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item, secrets) for item in value]
    return value


def _auth_error(message: str) -> ToolError:
    return ToolError(
        "AUTH_CONFIGURATION_INVALID", message, ExitCode.CONFIGURATION_ERROR
    )
