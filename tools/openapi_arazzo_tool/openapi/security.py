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

"""OpenAPI 3.1 security scheme and requirement validation."""

from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

from ..errors import ExitCode, ToolError
from .model import OpenApiDocument

_HTTP_METHODS = frozenset(
    {"delete", "get", "head", "options", "patch", "post", "put", "trace"}
)
_SECURITY_TYPES = frozenset({"apiKey", "http", "mutualTLS", "oauth2", "openIdConnect"})
_API_KEY_LOCATIONS = frozenset({"header", "query", "cookie"})
_OAUTH_FLOW_TYPES = frozenset(
    {"implicit", "password", "clientCredentials", "authorizationCode"}
)


def find_security_issues(document: OpenApiDocument) -> list[ToolError]:
    """Validate Security Scheme Objects and their Security Requirement usage."""
    issues: list[ToolError] = []
    schemes = _security_schemes(document.raw, document.path, issues)
    _validate_security_requirements(
        document.raw.get("security"), "$.security", schemes, document.path, issues
    )

    paths = document.raw.get("paths")
    if not isinstance(paths, Mapping):
        return issues
    for path, path_item in paths.items():
        if not isinstance(path, str) or not isinstance(path_item, Mapping):
            continue
        for method, operation in path_item.items():
            if method.lower() not in _HTTP_METHODS or not isinstance(
                operation, Mapping
            ):
                continue
            if "security" in operation:
                _validate_security_requirements(
                    operation["security"],
                    f"$.paths.{path}.{method}.security",
                    schemes,
                    document.path,
                    issues,
                )
    return issues


def _security_schemes(
    document: Mapping[str, Any], file_path: str, issues: list[ToolError]
) -> dict[str, Mapping[str, Any]]:
    components = document.get("components")
    if not isinstance(components, Mapping):
        return {}
    security_schemes = components.get("securitySchemes")
    if security_schemes is None:
        return {}
    if not isinstance(security_schemes, Mapping):
        _add_issue(
            issues,
            "$.components.securitySchemes",
            "Security Schemes must be a mapping.",
            file_path,
        )
        return {}

    schemes: dict[str, Mapping[str, Any]] = {}
    for name, scheme in security_schemes.items():
        path = f"$.components.securitySchemes.{name}"
        if not isinstance(name, str) or not name.strip():
            _add_issue(
                issues,
                path,
                "Security Scheme names must be non-empty strings.",
                file_path,
            )
            continue
        schemes[name] = scheme if isinstance(scheme, Mapping) else {}
        _validate_security_scheme(scheme, path, file_path, issues)
    return schemes


def _validate_security_scheme(
    scheme: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if not isinstance(scheme, Mapping):
        _add_issue(issues, path, "Security Scheme must be a mapping.", file_path)
        return
    scheme_type = scheme.get("type")
    if scheme_type not in _SECURITY_TYPES:
        _add_issue(
            issues,
            f"{path}.type",
            "Security Scheme type is not supported by OpenAPI 3.1.",
            file_path,
        )
        return
    if scheme_type == "apiKey":
        _require_non_empty_string(
            scheme.get("name"), f"{path}.name", "API key name", file_path, issues
        )
        if scheme.get("in") not in _API_KEY_LOCATIONS:
            _add_issue(
                issues,
                f"{path}.in",
                "API key location must be header, query, or cookie.",
                file_path,
            )
    elif scheme_type == "http":
        _require_non_empty_string(
            scheme.get("scheme"),
            f"{path}.scheme",
            "HTTP authentication scheme",
            file_path,
            issues,
        )
    elif scheme_type == "oauth2":
        flows = scheme.get("flows")
        if not isinstance(flows, Mapping) or not flows:
            _add_issue(
                issues,
                f"{path}.flows",
                "OAuth 2 Security Scheme requires a non-empty flows mapping.",
                file_path,
            )
        else:
            _validate_oauth_flows(flows, f"{path}.flows", file_path, issues)
    elif scheme_type == "openIdConnect":
        value = scheme.get("openIdConnectUrl")
        if not isinstance(value, str) or not urlsplit(value).scheme:
            _add_issue(
                issues,
                f"{path}.openIdConnectUrl",
                "OpenID Connect URL must be an absolute URI.",
                file_path,
            )


def _validate_security_requirements(
    requirements: Any,
    path: str,
    schemes: Mapping[str, Mapping[str, Any]],
    file_path: str,
    issues: list[ToolError],
) -> None:
    if requirements is None:
        return
    if not _is_sequence(requirements):
        _add_issue(issues, path, "Security Requirements must be an array.", file_path)
        return
    for index, requirement in enumerate(requirements):
        requirement_path = f"{path}[{index}]"
        if not isinstance(requirement, Mapping):
            _add_issue(
                issues,
                requirement_path,
                "Security Requirement must be a mapping.",
                file_path,
            )
            continue
        for name, scopes in requirement.items():
            scheme_path = f"{requirement_path}.{name}"
            if name not in schemes:
                _add_issue(
                    issues,
                    scheme_path,
                    f"Security Scheme '{name}' is not defined.",
                    file_path,
                )
            if not _is_sequence(scopes):
                _add_issue(
                    issues,
                    scheme_path,
                    "Security Requirement scopes must be an array.",
                    file_path,
                )
                continue
            scheme = schemes.get(name)
            if scheme is not None:
                _validate_requirement_scopes(
                    scopes, scheme, scheme_path, file_path, issues
                )


def _validate_oauth_flows(
    flows: Mapping[str, Any], path: str, file_path: str, issues: list[ToolError]
) -> None:
    for flow_type, flow in flows.items():
        flow_path = f"{path}.{flow_type}"
        if flow_type not in _OAUTH_FLOW_TYPES:
            _add_issue(
                issues,
                flow_path,
                "OAuth 2 flow type is not supported by OpenAPI 3.1.",
                file_path,
            )
            continue
        if not isinstance(flow, Mapping):
            _add_issue(issues, flow_path, "OAuth 2 flow must be a mapping.", file_path)
            continue
        scopes = flow.get("scopes")
        if not isinstance(scopes, Mapping):
            _add_issue(
                issues,
                f"{flow_path}.scopes",
                "OAuth 2 flow requires a scopes mapping.",
                file_path,
            )
        if flow_type in {"implicit", "authorizationCode"}:
            _require_absolute_uri(
                flow.get("authorizationUrl"),
                f"{flow_path}.authorizationUrl",
                file_path,
                issues,
            )
        if flow_type in {"password", "clientCredentials", "authorizationCode"}:
            _require_absolute_uri(
                flow.get("tokenUrl"), f"{flow_path}.tokenUrl", file_path, issues
            )


def _validate_requirement_scopes(
    scopes: Sequence[Any],
    scheme: Mapping[str, Any],
    path: str,
    file_path: str,
    issues: list[ToolError],
) -> None:
    if scheme.get("type") != "oauth2":
        if scopes:
            _add_issue(
                issues,
                path,
                "Only OAuth 2 Security Requirements may declare scopes.",
                file_path,
            )
        return
    known_scopes = _oauth_scopes(scheme.get("flows"))
    for index, scope in enumerate(scopes):
        scope_path = f"{path}[{index}]"
        if not isinstance(scope, str):
            _add_issue(issues, scope_path, "OAuth 2 scope must be a string.", file_path)
        elif scope not in known_scopes:
            _add_issue(
                issues,
                scope_path,
                f"OAuth 2 scope '{scope}' is not declared by the Security Scheme.",
                file_path,
            )


def _oauth_scopes(flows: Any) -> set[str]:
    if not isinstance(flows, Mapping):
        return set()
    return {
        scope
        for flow in flows.values()
        if isinstance(flow, Mapping) and isinstance(flow.get("scopes"), Mapping)
        for scope in flow["scopes"]
        if isinstance(scope, str)
    }


def _require_absolute_uri(
    value: Any, path: str, file_path: str, issues: list[ToolError]
) -> None:
    if not isinstance(value, str) or not urlsplit(value).scheme:
        _add_issue(issues, path, "URL must be an absolute URI.", file_path)


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


def _require_non_empty_string(
    value: Any, path: str, label: str, file_path: str, issues: list[ToolError]
) -> None:
    if not isinstance(value, str) or not value.strip():
        _add_issue(issues, path, f"{label} must be a non-empty string.", file_path)


def _add_issue(
    issues: list[ToolError], path: str, message: str, file_path: str
) -> None:
    issues.append(
        ToolError(
            "OPENAPI_SECURITY_INVALID",
            f"{message} Found at {path}.",
            ExitCode.VALIDATION_ERROR,
            file_path,
        )
    )
