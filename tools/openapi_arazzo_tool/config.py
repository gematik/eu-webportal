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

from pathlib import Path
from typing import Any

import yaml

from .errors import ExitCode, ToolError


def load_config(filename: str = "tool.yaml", cwd: Path | None = None) -> dict[str, Any]:
    base = cwd or Path.cwd()
    path = Path(filename)
    if not path.is_absolute():
        path = base / path

    if not path.exists():
        if filename == "tool.yaml":
            return {}
        raise ToolError(
            "CONFIG_INVALID",
            f"Configuration file does not exist: {filename}",
            ExitCode.CONFIGURATION_ERROR,
            str(path),
        )

    try:
        with path.open(encoding="utf-8") as stream:
            config = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as error:
        raise ToolError(
            "CONFIG_INVALID",
            f"Unable to parse configuration: {error}",
            ExitCode.CONFIGURATION_ERROR,
            str(path),
        ) from error

    if config is None:
        return {}
    if not isinstance(config, dict):
        raise ToolError(
            "CONFIG_INVALID",
            "Configuration root must be a mapping.",
            ExitCode.CONFIGURATION_ERROR,
            str(path),
        )
    return config
