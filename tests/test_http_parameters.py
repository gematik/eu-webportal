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

from tools.openapi_arazzo_tool.errors import ExitCode, ToolError
from tools.openapi_arazzo_tool.http.parameters import serialize_parameters


class HttpParameterSerializationTest(unittest.TestCase):
    def test_serializes_default_path_query_header_and_cookie_styles(self) -> None:
        result = serialize_parameters(
            "/widgets/{id}",
            [
                {"name": "id", "in": "path", "required": True},
                {"name": "tag", "in": "query"},
                {"name": "X-Trace", "in": "header"},
                {"name": "session", "in": "cookie"},
            ],
            {
                ("id", "path"): "a/b",
                ("tag", "query"): ["red", "blue"],
                ("X-Trace", "header"): "trace-1",
                ("session", "cookie"): "abc",
            },
        )

        self.assertEqual(result.path, "/widgets/a%2Fb")
        self.assertEqual(result.query, (("tag", "red"), ("tag", "blue")))
        self.assertEqual(result.headers, {"X-Trace": "trace-1"})
        self.assertEqual(result.cookies, {"session": "abc"})

    def test_serializes_path_label_and_matrix_objects(self) -> None:
        label = serialize_parameters(
            "/widgets/{id}",
            [{"name": "id", "in": "path", "style": "label", "explode": True}],
            {("id", "path"): {"region": "eu", "id": 42}},
        )
        matrix = serialize_parameters(
            "/widgets/{id}",
            [{"name": "id", "in": "path", "style": "matrix", "explode": True}],
            {("id", "path"): ["a", "b"]},
        )

        self.assertEqual(label.path, "/widgets/.region=eu.id=42")
        self.assertEqual(matrix.path, "/widgets/;id=a;id=b")

    def test_serializes_form_deep_object_and_delimited_query_values(self) -> None:
        result = serialize_parameters(
            "/widgets",
            [
                {
                    "name": "filter",
                    "in": "query",
                    "style": "deepObject",
                    "explode": True,
                },
                {
                    "name": "space",
                    "in": "query",
                    "style": "spaceDelimited",
                    "explode": False,
                },
                {
                    "name": "pipe",
                    "in": "query",
                    "style": "pipeDelimited",
                    "explode": False,
                },
            ],
            {
                ("filter", "query"): {"state": "ready", "owner": "A B"},
                ("space", "query"): ["a", "b"],
                ("pipe", "query"): ["a", "b"],
            },
        )

        self.assertEqual(
            result.query,
            (
                ("filter%5Bstate%5D", "ready"),
                ("filter%5Bowner%5D", "A%20B"),
                ("space", "a%20b"),
                ("pipe", "a%7Cb"),
            ),
        )

    def test_applies_allow_reserved_only_to_query_values(self) -> None:
        result = serialize_parameters(
            "/widgets",
            [{"name": "next page", "in": "query", "allowReserved": True}],
            {("next page", "query"): "/widgets?page=2"},
        )

        self.assertEqual(result.query, (("next%20page", "/widgets?page=2"),))

    def test_serializes_simple_header_objects_and_cookie_objects(self) -> None:
        result = serialize_parameters(
            "/widgets",
            [
                {
                    "name": "X-Filter",
                    "in": "header",
                    "style": "simple",
                    "explode": True,
                },
                {"name": "prefs", "in": "cookie", "style": "form", "explode": True},
            ],
            {
                ("X-Filter", "header"): {"state": "ready", "limit": 10},
                ("prefs", "cookie"): {"theme": "dark", "page": 2},
            },
        )

        self.assertEqual(result.headers, {"X-Filter": "state=ready,limit=10"})
        self.assertEqual(result.cookies, {"theme": "dark", "page": "2"})

    def test_fails_for_missing_required_or_invalid_style_values(self) -> None:
        with self.assertRaises(ToolError) as missing:
            serialize_parameters(
                "/widgets/{id}",
                [{"name": "id", "in": "path", "required": True}],
                {},
            )
        with self.assertRaises(ToolError) as invalid:
            serialize_parameters(
                "/widgets",
                [
                    {
                        "name": "filter",
                        "in": "query",
                        "style": "deepObject",
                        "explode": False,
                    }
                ],
                {("filter", "query"): {"state": "ready"}},
            )

        self.assertEqual(missing.exception.code, "HTTP_PARAMETER_SERIALIZATION_FAILED")
        self.assertEqual(missing.exception.exit_code, ExitCode.TEST_ERROR)
        self.assertEqual(invalid.exception.code, "HTTP_PARAMETER_SERIALIZATION_FAILED")
