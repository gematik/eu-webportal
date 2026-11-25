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
from pathlib import Path

from tools.openapi_arazzo_tool.arazzo.loader import load_arazzo_document
from tools.openapi_arazzo_tool.cross_validation.parameters import find_parameter_issues
from tools.openapi_arazzo_tool.cross_validation.request_bodies import (
    find_request_body_issues,
)
from tools.openapi_arazzo_tool.cross_validation.sources import resolve_sources

FIXTURES = Path(__file__).parent / "fixtures" / "cross"


class ArazzoParameterValidationTest(unittest.TestCase):
    def test_accepts_defined_parameters_in_correct_locations(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "valid" / "parameters-workflow.yaml")
        )
        sources = resolve_sources(document, [str(FIXTURES)])

        self.assertEqual(sources.issues, [])
        self.assertEqual(find_parameter_issues(document, sources), [])

    def test_rejects_unknown_wrong_location_and_missing_required_parameters(
        self,
    ) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "invalid-parameters.yaml")
        )
        sources = resolve_sources(document, [str(FIXTURES)])

        issues = find_parameter_issues(document, sources)

        self.assertEqual(len(issues), 4)
        self.assertTrue(
            all(issue.code == "ARAZZO_PARAMETER_UNRESOLVED" for issue in issues)
        )
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("Parameter 'id' in 'query' is not defined", messages)
        self.assertIn("Parameter 'unknown' in 'header' is not defined", messages)
        self.assertIn("Required parameter 'id' in 'path' is not supplied", messages)
        self.assertIn(
            "Required parameter 'locale' in 'query' is not supplied", messages
        )

    def test_rejects_static_values_that_do_not_match_parameter_schemas(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "invalid-parameter-values.yaml")
        )
        sources = resolve_sources(document, [str(FIXTURES)])

        issues = find_parameter_issues(document, sources)

        self.assertEqual(
            {issue.code for issue in issues}, {"ARAZZO_PARAMETER_VALUE_INVALID"}
        )
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("locale", messages)
        self.assertIn("page", messages)

    def test_defers_runtime_expression_values(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "valid" / "parameters-workflow.yaml")
        )
        document.raw["workflows"][0]["steps"][0]["parameters"][1]["value"] = (
            "{$inputs.locale}"
        )
        sources = resolve_sources(document, [str(FIXTURES)])

        self.assertEqual(find_parameter_issues(document, sources), [])

    def test_accepts_schema_compatible_request_body(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "valid" / "request-body-workflow.yaml")
        )
        sources = resolve_sources(document, [str(FIXTURES)])

        self.assertEqual(find_request_body_issues(document, sources), [])

    def test_rejects_unsupported_request_body_content_type(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "invalid-request-body.yaml")
        )
        sources = resolve_sources(document, [str(FIXTURES)])

        issues = find_request_body_issues(document, sources)

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].code, "ARAZZO_REQUEST_BODY_INVALID")
        self.assertIn("text/plain", issues[0].message)
