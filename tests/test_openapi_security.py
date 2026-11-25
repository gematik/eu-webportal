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

from tools.openapi_arazzo_tool.openapi.loader import load_openapi_document
from tools.openapi_arazzo_tool.openapi.security import find_security_issues

FIXTURES = Path(__file__).parent / "fixtures" / "openapi"


class OpenApiSecurityValidationTest(unittest.TestCase):
    def test_accepts_security_scheme_alternatives_and_combinations(self) -> None:
        document = load_openapi_document(
            str(FIXTURES / "valid" / "valid-security.yaml")
        )

        self.assertEqual(find_security_issues(document), [])

    def test_collects_invalid_schemes_and_requirements(self) -> None:
        document = load_openapi_document(
            str(FIXTURES / "invalid" / "invalid-security.yaml")
        )

        issues = find_security_issues(document)

        self.assertEqual(len(issues), 11)
        self.assertTrue(
            all(issue.code == "OPENAPI_SECURITY_INVALID" for issue in issues)
        )
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("$.components.securitySchemes.BrokenApiKey.name", messages)
        self.assertIn("$.components.securitySchemes.BrokenApiKey.in", messages)
        self.assertIn("$.components.securitySchemes.BrokenHttp.scheme", messages)
        self.assertIn(
            "$.components.securitySchemes.BrokenOAuth.flows.clientCredentials.tokenUrl",
            messages,
        )
        self.assertIn(
            "$.components.securitySchemes.BrokenOidc.openIdConnectUrl", messages
        )
        self.assertIn("$.components.securitySchemes.Unsupported.type", messages)
        self.assertIn("Security Scheme 'Unknown' is not defined", messages)
        self.assertIn("$.security[1].BrokenApiKey", messages)
        self.assertIn("Only OAuth 2 Security Requirements may declare scopes", messages)
        self.assertIn("OAuth 2 scope 'missing-scope'", messages)
        self.assertIn("$.paths./widgets.get.security", messages)
