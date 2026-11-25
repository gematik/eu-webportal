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

import re
from pathlib import Path
from typing import Any

import yaml

from ..errors import ExitCode, ToolError
from .model import OpenApiDocument

SUPPORTED_VERSION_PATTERN = re.compile(r"^3\.1\.\d+$")


def load_openapi_document(path: str) -> OpenApiDocument:
    """Load and version-check a single OpenAPI document.

    Only local files are read. Syntax errors and unsupported OpenAPI
    versions are rejected explicitly and never silently ignored, per the
    V1 requirements. Schema/$ref validation is out of scope for this step
    and is added in later increments of Milestone 1.
    """
    file_path = Path(path)

    if not file_path.exists():
        raise ToolError(
            "OPENAPI_FILE_NOT_FOUND",
            f"OpenAPI document does not exist: {path}",
            ExitCode.VALIDATION_ERROR,
            str(file_path),
        )

    try:
        with file_path.open(encoding="utf-8") as stream:
            raw: Any = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as error:
        raise ToolError(
            "OPENAPI_SYNTAX_INVALID",
            f"Unable to parse OpenAPI document: {error}",
            ExitCode.VALIDATION_ERROR,
            str(file_path),
        ) from error

    if not isinstance(raw, dict):
        raise ToolError(
            "OPENAPI_SYNTAX_INVALID",
            "OpenAPI document root must be a mapping.",
            ExitCode.VALIDATION_ERROR,
            str(file_path),
        )

    version = raw.get("openapi")
    if not isinstance(version, str) or not SUPPORTED_VERSION_PATTERN.match(version):
        raise ToolError(
            "OPENAPI_VERSION_UNSUPPORTED",
            f"OpenAPI version {version!r} is not supported. Supported versions: 3.1.x.",
            ExitCode.VALIDATION_ERROR,
            str(file_path),
        )

    return OpenApiDocument(path=str(file_path), version=version, raw=raw)
