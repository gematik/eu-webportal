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

import unittest

from tools.openapi_arazzo_tool.errors import ToolError
from tools.openapi_arazzo_tool.http.targets import (
    resolve_operation_url,
    resolve_target_url,
)


class HttpTargetResolutionTest(unittest.TestCase):
    def test_applies_target_precedence_and_server_variables(self) -> None:
        document = {
            "servers": [{"url": "https://root.example.test"}],
        }
        path_item = {
            "servers": [
                {
                    "url": "{scheme}://path.example.test/{base}",
                    "variables": {
                        "scheme": {"default": "https", "enum": ["https"]},
                        "base": {"default": "v1"},
                    },
                }
            ],
        }
        operation = {"servers": [{"url": "https://operation.example.test"}]}

        self.assertEqual(
            resolve_target_url(document, path_item, operation),
            "https://operation.example.test",
        )
        self.assertEqual(
            resolve_target_url(
                document, path_item, {}, server_variables={"base": "v2"}
            ),
            "https://path.example.test/v2",
        )
        self.assertEqual(
            resolve_target_url(
                document,
                path_item,
                operation,
                configured_base_url="http://localhost:8080",
            ),
            "http://localhost:8080",
        )

    def test_combines_base_and_operation_path(self) -> None:
        self.assertEqual(
            resolve_operation_url("https://example.test/api/v1", "/widgets/42"),
            "https://example.test/api/v1/widgets/42",
        )

    def test_rejects_missing_invalid_or_unresolved_targets(self) -> None:
        invalid = (
            lambda: resolve_target_url({}, {}, {}),
            lambda: resolve_target_url(
                {}, {}, {}, configured_base_url="file:///tmp/api"
            ),
            lambda: resolve_target_url(
                {"servers": [{"url": "https://{host}", "variables": {}}]},
                {},
                {},
            ),
        )
        for resolve in invalid:
            with self.subTest(resolve=resolve), self.assertRaises(ToolError):
                resolve()
