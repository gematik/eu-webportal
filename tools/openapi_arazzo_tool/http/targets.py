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

"""Deterministic OpenAPI target resolution."""

import re
from collections.abc import Mapping, Sequence
from typing import Any, TypeGuard
from urllib.parse import urljoin, urlsplit

from ..errors import ExitCode, ToolError

_VARIABLE = re.compile(r"\{([^{}]+)\}")


def resolve_target_url(
    document: Mapping[str, Any],
    path_item: Mapping[str, Any],
    operation: Mapping[str, Any],
    *,
    configured_base_url: str | None = None,
    server_variables: Mapping[str, str] | None = None,
) -> str:
    """Resolve target base URL using the required precedence."""
    if configured_base_url:
        return _absolute_http_url(configured_base_url)
    for owner in (operation, path_item, document):
        servers = owner.get("servers")
        if _is_sequence(servers) and servers:
            server = servers[0]
            if not isinstance(server, Mapping):
                raise _target_error("OpenAPI Server Object must be a mapping.")
            return _resolve_server(server, server_variables or {})
    raise _target_error("No target base URL or OpenAPI server is available.")


def resolve_operation_url(base_url: str, operation_path: str) -> str:
    """Combine an absolute target base URL and serialized operation path."""
    base = _absolute_http_url(base_url)
    return urljoin(f"{base.rstrip('/')}/", operation_path.lstrip("/"))


def _resolve_server(server: Mapping[str, Any], overrides: Mapping[str, str]) -> str:
    template = server.get("url")
    if not isinstance(template, str) or not template.strip():
        raise _target_error("OpenAPI server URL must be a non-empty string.")
    variables = server.get("variables")
    variable_definitions = variables if isinstance(variables, Mapping) else {}

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        definition = variable_definitions.get(name)
        if not isinstance(definition, Mapping):
            raise _target_error(f"Server variable '{name}' is not defined.")
        value = overrides.get(name, definition.get("default"))
        if not isinstance(value, str):
            raise _target_error(f"Server variable '{name}' has no resolved value.")
        enum = definition.get("enum")
        if _is_sequence(enum) and value not in enum:
            raise _target_error(
                f"Server variable '{name}' value '{value}' is not allowed."
            )
        return value

    resolved = _VARIABLE.sub(replace, template)
    if _VARIABLE.search(resolved):
        raise _target_error("OpenAPI server URL contains unresolved variables.")
    return _absolute_http_url(resolved)


def _absolute_http_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise _target_error("Target URL must be an absolute HTTP or HTTPS URL.")
    if parsed.username or parsed.password or parsed.fragment:
        raise _target_error("Target URL must not contain user info or fragments.")
    return value


def _is_sequence(value: Any) -> TypeGuard[Sequence[Any]]:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


def _target_error(message: str) -> ToolError:
    return ToolError("TARGET_RESOLUTION_FAILED", message, ExitCode.TEST_ERROR)
