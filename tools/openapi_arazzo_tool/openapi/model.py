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

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OpenApiDocument:
    """Minimal internal representation of a loaded OpenAPI 3.1.x document.

    Only the version and the raw parsed content are captured here. Further
    milestones will translate ``raw`` into a richer internal model (paths,
    operations, schemas, ...) instead of exposing the YAML/JSON structure
    throughout the codebase.
    """

    path: str
    version: str
    raw: dict[str, Any]
