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

"""OpenAPI 3.1 parameter serialization for HTTP requests."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

from ..errors import ExitCode, ToolError

_RESERVED = ":/?#[]@!$&'()*+,;="
_UNRESERVED = "-._~"
_DEFAULT_STYLES = {
    "path": "simple",
    "query": "form",
    "header": "simple",
    "cookie": "form",
}
_ALLOWED_STYLES = {
    "path": frozenset({"simple", "label", "matrix"}),
    "query": frozenset({"form", "spaceDelimited", "pipeDelimited", "deepObject"}),
    "header": frozenset({"simple"}),
    "cookie": frozenset({"form"}),
}


@dataclass(frozen=True)
class SerializedParameters:
    """HTTP request parts produced from OpenAPI Parameter Objects."""

    path: str
    query: tuple[tuple[str, str], ...] = ()
    headers: Mapping[str, str] = field(default_factory=dict)
    cookies: Mapping[str, str] = field(default_factory=dict)


def serialize_parameters(
    path_template: str,
    parameters: Sequence[Mapping[str, Any]],
    values: Mapping[tuple[str, str], Any],
) -> SerializedParameters:
    """Serialize supplied values according to effective OpenAPI parameters."""
    path = path_template
    query: list[tuple[str, str]] = []
    headers: dict[str, str] = {}
    cookies: dict[str, str] = {}

    for parameter in parameters:
        name = parameter.get("name")
        location = parameter.get("in")
        if not isinstance(name, str) or location not in _DEFAULT_STYLES:
            raise _serialization_error(
                "Parameter must define a valid name and location."
            )
        key = (name, location)
        if key not in values:
            if parameter.get("required") is True:
                raise _serialization_error(
                    f"Required parameter '{name}' in '{location}' is missing."
                )
            continue

        style = parameter.get("style", _DEFAULT_STYLES[location])
        if style not in _ALLOWED_STYLES[location]:
            raise _serialization_error(
                f"Style '{style}' is not supported for parameter '{name}' in '{location}'."
            )
        explode = parameter.get("explode", style == "form")
        if not isinstance(explode, bool):
            raise _serialization_error(f"Parameter '{name}' explode must be a boolean.")
        value = values[key]

        if location == "path":
            marker = f"{{{name}}}"
            if marker not in path:
                raise _serialization_error(
                    f"Path parameter '{name}' has no matching template expression."
                )
            path = path.replace(marker, _serialize_path(name, value, style, explode))
        elif location == "query":
            query.extend(_serialize_query(parameter, value, style, explode))
        elif location == "header":
            headers[name] = _serialize_simple(value, explode, encode=False)
        else:
            cookies.update(_serialize_cookie(name, value, explode))

    if "{" in path or "}" in path:
        raise _serialization_error("Not all path template expressions were resolved.")
    return SerializedParameters(path, tuple(query), headers, cookies)


def _serialize_path(name: str, value: Any, style: str, explode: bool) -> str:
    if style == "simple":
        return _serialize_simple(value, explode, encode=True)
    if style == "label":
        return f".{_serialize_label(value, explode)}"
    return _serialize_matrix(name, value, explode)


def _serialize_simple(value: Any, explode: bool, *, encode: bool) -> str:
    def scalar(item: object) -> str:
        return _encode(item) if encode else _stringify(item)

    if _is_array(value):
        return ",".join(scalar(item) for item in value)
    if isinstance(value, Mapping):
        if explode:
            return ",".join(
                f"{scalar(key)}={scalar(item)}" for key, item in value.items()
            )
        return ",".join(
            part for key, item in value.items() for part in (scalar(key), scalar(item))
        )
    return scalar(value)


def _serialize_label(value: Any, explode: bool) -> str:
    if _is_array(value):
        separator = "." if explode else ","
        return separator.join(_encode(item) for item in value)
    if isinstance(value, Mapping):
        if explode:
            return ".".join(
                f"{_encode(key)}={_encode(item)}" for key, item in value.items()
            )
        return ",".join(
            part
            for key, item in value.items()
            for part in (_encode(key), _encode(item))
        )
    return _encode(value)


def _serialize_matrix(name: str, value: Any, explode: bool) -> str:
    encoded_name = _encode(name)
    if _is_array(value):
        if explode:
            return "".join(f";{encoded_name}={_encode(item)}" for item in value)
        return f";{encoded_name}={','.join(_encode(item) for item in value)}"
    if isinstance(value, Mapping):
        if explode:
            return "".join(
                f";{_encode(key)}={_encode(item)}" for key, item in value.items()
            )
        flattened = ",".join(
            part
            for key, item in value.items()
            for part in (_encode(key), _encode(item))
        )
        return f";{encoded_name}={flattened}"
    return f";{encoded_name}={_encode(value)}"


def _serialize_query(
    parameter: Mapping[str, Any],
    value: Any,
    style: str,
    explode: bool,
) -> list[tuple[str, str]]:
    name = parameter["name"]
    allow_reserved = parameter.get("allowReserved", False)
    if not isinstance(allow_reserved, bool):
        raise _serialization_error(
            f"Parameter '{name}' allowReserved must be a boolean."
        )

    def encode_value(item: object) -> str:
        return _encode(item, allow_reserved=allow_reserved)

    encoded_name = _encode(name)

    if style == "deepObject":
        if not isinstance(value, Mapping) or not explode:
            raise _serialization_error(
                f"deepObject parameter '{name}' requires an object value and explode=true."
            )
        return [
            (f"{encoded_name}%5B{_encode(key)}%5D", encode_value(item))
            for key, item in value.items()
        ]
    if style in {"spaceDelimited", "pipeDelimited"}:
        if not _is_array(value):
            raise _serialization_error(
                f"{style} parameter '{name}' requires an array value."
            )
        separator = "%20" if style == "spaceDelimited" else "%7C"
        return [(encoded_name, separator.join(encode_value(item) for item in value))]
    if _is_array(value):
        if explode:
            return [(encoded_name, encode_value(item)) for item in value]
        return [(encoded_name, ",".join(encode_value(item) for item in value))]
    if isinstance(value, Mapping):
        if explode:
            return [(_encode(key), encode_value(item)) for key, item in value.items()]
        flattened = ",".join(
            part
            for key, item in value.items()
            for part in (_encode(key), encode_value(item))
        )
        return [(encoded_name, flattened)]
    return [(encoded_name, encode_value(value))]


def _serialize_cookie(name: str, value: Any, explode: bool) -> dict[str, str]:
    if _is_array(value):
        return {name: ",".join(_stringify(item) for item in value)}
    if isinstance(value, Mapping):
        if explode:
            return {str(key): _stringify(item) for key, item in value.items()}
        return {
            name: ",".join(
                part
                for key, item in value.items()
                for part in (_stringify(key), _stringify(item))
            )
        }
    return {name: _stringify(value)}


def _encode(value: Any, *, allow_reserved: bool = False) -> str:
    safe = f"{_UNRESERVED}{_RESERVED if allow_reserved else ''}"
    return quote(_stringify(value), safe=safe)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


def _is_array(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )


def _serialization_error(message: str) -> ToolError:
    return ToolError(
        "HTTP_PARAMETER_SERIALIZATION_FAILED",
        message,
        ExitCode.TEST_ERROR,
    )
