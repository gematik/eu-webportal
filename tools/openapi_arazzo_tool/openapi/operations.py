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

"""OpenAPI operation-level validation."""

from collections.abc import Mapping

from ..errors import ExitCode, ToolError
from .model import OpenApiDocument

_HTTP_METHODS = frozenset(
    {"delete", "get", "head", "options", "patch", "post", "put", "trace"}
)


def find_operation_id_issues(document: OpenApiDocument) -> list[ToolError]:
    """Return an issue for every duplicated OpenAPI operationId.

    An operationId is scoped to the complete OpenAPI document, not to an
    individual path or HTTP method. The check intentionally inspects only
    OpenAPI operation objects beneath ``paths``; extension fields and other
    arbitrary mappings do not define operations.
    """
    paths = document.raw.get("paths")
    if not isinstance(paths, Mapping):
        return []

    first_locations: dict[str, str] = {}
    issues: list[ToolError] = []
    for path, path_item in paths.items():
        if not isinstance(path_item, Mapping):
            continue
        for method, operation in path_item.items():
            if method.lower() not in _HTTP_METHODS or not isinstance(
                operation, Mapping
            ):
                continue
            operation_id = operation.get("operationId")
            if not isinstance(operation_id, str):
                continue

            location = f"$.paths.{path}.{method}.operationId"
            first_location = first_locations.setdefault(operation_id, location)
            if first_location == location:
                continue
            issues.append(
                ToolError(
                    "OPENAPI_OPERATION_ID_DUPLICATE",
                    f"operationId '{operation_id}' is duplicated at {location}; "
                    f"first declared at {first_location}.",
                    ExitCode.VALIDATION_ERROR,
                    document.path,
                )
            )
    return issues
