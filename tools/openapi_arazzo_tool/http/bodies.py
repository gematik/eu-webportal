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

"""Media-type-specific OpenAPI request body serialization."""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus

from ..errors import ExitCode, ToolError

_DEFAULT_BOUNDARY = "openapi-arazzo-boundary"
_RESERVED = ":/?#[]@!$&'()*+,;="


@dataclass(frozen=True)
class SerializedBody:
    """Serialized HTTP body and its final Content-Type header value."""

    content_type: str
    data: bytes


def serialize_request_body(
    payload: Any,
    content_type: str,
    encoding: Mapping[str, Mapping[str, Any]] | None = None,
    *,
    multipart_boundary: str | None = None,
) -> SerializedBody:
    """Serialize a payload according to its OpenAPI media type."""
    media_type = content_type.partition(";")[0].strip().lower()
    if media_type == "application/json" or media_type.endswith("+json"):
        return SerializedBody(content_type, _json_bytes(payload))
    if media_type == "application/x-www-form-urlencoded":
        return SerializedBody(content_type, _form_bytes(payload, encoding or {}))
    if media_type == "multipart/form-data":
        boundary = multipart_boundary or _DEFAULT_BOUNDARY
        _validate_boundary(boundary)
        data = _multipart_bytes(payload, encoding or {}, boundary)
        return SerializedBody(f"multipart/form-data; boundary={boundary}", data)
    if media_type == "application/octet-stream":
        return SerializedBody(content_type, _binary_bytes(payload))
    if (
        media_type.startswith("text/")
        or media_type.endswith("+xml")
        or media_type
        in {
            "application/xml",
        }
    ):
        return SerializedBody(content_type, _text_bytes(payload))
    raise _serialization_error(
        f"Request body media type '{content_type}' is not supported."
    )


def _json_bytes(payload: Any) -> bytes:
    try:
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise _serialization_error(
            f"JSON request body cannot be serialized: {error}"
        ) from error


def _form_bytes(
    payload: Any,
    encoding: Mapping[str, Mapping[str, Any]],
) -> bytes:
    if not isinstance(payload, Mapping):
        raise _serialization_error("Form request body payload must be a mapping.")
    parts: list[str] = []
    for name, value in payload.items():
        if not isinstance(name, str):
            raise _serialization_error("Form field names must be strings.")
        rules = encoding.get(name, {})
        style = rules.get("style", "form")
        explode = rules.get("explode", True)
        allow_reserved = rules.get("allowReserved", False)
        if (
            style != "form"
            or not isinstance(explode, bool)
            or not isinstance(allow_reserved, bool)
        ):
            raise _serialization_error(
                f"Form field '{name}' has unsupported encoding configuration."
            )
        parts.extend(_form_parts(name, value, explode, allow_reserved))
    return "&".join(parts).encode("ascii")


def _form_parts(
    name: str, value: Any, explode: bool, allow_reserved: bool
) -> list[str]:
    encoded_name = _form_encode(name, False)

    def encode_value(item: object) -> str:
        return _form_encode(_stringify(item), allow_reserved)

    if _is_array(value):
        if explode:
            return [f"{encoded_name}={encode_value(item)}" for item in value]
        return [f"{encoded_name}={','.join(encode_value(item) for item in value)}"]
    if isinstance(value, Mapping):
        if explode:
            return [
                f"{_form_encode(str(key), False)}={encode_value(item)}"
                for key, item in value.items()
            ]
        flattened = ",".join(
            part
            for key, item in value.items()
            for part in (_form_encode(str(key), False), encode_value(item))
        )
        return [f"{encoded_name}={flattened}"]
    return [f"{encoded_name}={encode_value(value)}"]


def _multipart_bytes(
    payload: Any,
    encoding: Mapping[str, Mapping[str, Any]],
    boundary: str,
) -> bytes:
    if not isinstance(payload, Mapping):
        raise _serialization_error("Multipart request body payload must be a mapping.")
    boundary_bytes = boundary.encode("ascii")
    chunks: list[bytes] = []
    for name, value in payload.items():
        if not isinstance(name, str):
            raise _serialization_error("Multipart field names must be strings.")
        _reject_header_injection(name, "Multipart field name")
        values = value if _is_array(value) else [value]
        rules = encoding.get(name, {})
        part_content_type = rules.get("contentType")
        if part_content_type is not None and not isinstance(part_content_type, str):
            raise _serialization_error(
                f"Multipart field '{name}' contentType must be a string."
            )
        for item in values:
            item_content_type = part_content_type or _default_part_content_type(item)
            _reject_header_injection(item_content_type, "Multipart Content-Type")
            data = _part_bytes(item, item_content_type)
            if boundary_bytes in data:
                raise _serialization_error(
                    f"Multipart boundary collides with payload for field '{name}'."
                )
            chunks.extend(
                (
                    b"--" + boundary_bytes + b"\r\n",
                    f'Content-Disposition: form-data; name="{name}"\r\n'.encode(
                        "ascii"
                    ),
                    f"Content-Type: {item_content_type}\r\n\r\n".encode("ascii"),
                    data,
                    b"\r\n",
                )
            )
    chunks.append(b"--" + boundary_bytes + b"--\r\n")
    return b"".join(chunks)


def _part_bytes(value: Any, content_type: str) -> bytes:
    media_type = content_type.partition(";")[0].strip().lower()
    if media_type == "application/json" or media_type.endswith("+json"):
        return _json_bytes(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    if isinstance(value, (bool, int, float)) or value is None:
        return _stringify(value).encode("utf-8")
    raise _serialization_error(
        f"Multipart value requires JSON contentType or scalar/binary data, got {type(value).__name__}."
    )


def _default_part_content_type(value: Any) -> str:
    if isinstance(value, Mapping):
        return "application/json"
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "application/octet-stream"
    return "text/plain; charset=utf-8"


def _binary_bytes(payload: Any) -> bytes:
    if isinstance(payload, (bytes, bytearray, memoryview)):
        return bytes(payload)
    raise _serialization_error("Binary request body payload must be bytes-like.")


def _text_bytes(payload: Any) -> bytes:
    if isinstance(payload, str):
        return payload.encode("utf-8")
    if isinstance(payload, (bytes, bytearray, memoryview)):
        return bytes(payload)
    raise _serialization_error(
        "Text or XML request body payload must be text or bytes-like."
    )


def _form_encode(value: str, allow_reserved: bool) -> str:
    return quote_plus(value, safe=_RESERVED if allow_reserved else "")


def _validate_boundary(boundary: str) -> None:
    if (
        not boundary
        or len(boundary) > 70
        or not boundary.isascii()
        or any(character in boundary for character in '\r\n"')
    ):
        raise _serialization_error("Multipart boundary is invalid.")


def _reject_header_injection(value: str, label: str) -> None:
    if "\r" in value or "\n" in value:
        raise _serialization_error(f"{label} must not contain CR or LF characters.")


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
        "HTTP_BODY_SERIALIZATION_FAILED",
        message,
        ExitCode.TEST_ERROR,
    )
