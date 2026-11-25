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

from tools.openapi_arazzo_tool.arazzo.criterion_features import (
    find_criterion_feature_issues,
)
from tools.openapi_arazzo_tool.arazzo.loader import load_arazzo_document

FIXTURES = Path(__file__).parent / "fixtures" / "arazzo"


class ArazzoCriterionFeatureValidationTest(unittest.TestCase):
    def test_accepts_simple_criteria_without_context(self) -> None:
        document = load_arazzo_document(str(FIXTURES / "valid" / "valid-actions.yaml"))

        self.assertEqual(find_criterion_feature_issues(document), [])

    def test_rejects_unsupported_and_unknown_criterion_features(self) -> None:
        document = load_arazzo_document(
            str(FIXTURES / "invalid" / "unsupported-criterion-features.yaml")
        )

        issues = find_criterion_feature_issues(document)

        self.assertEqual(len(issues), 6)
        self.assertEqual(
            [issue.code for issue in issues].count("ARAZZO_FEATURE_UNSUPPORTED"),
            5,
        )
        self.assertEqual(
            [issue.code for issue in issues].count("ARAZZO_CRITERION_INVALID"),
            1,
        )
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("Criterion type 'jsonpath'", messages)
        self.assertIn("Criterion Expression Type Objects", messages)
        self.assertIn("Unknown Criterion type 'custom'", messages)
        self.assertIn("Criterion type 'xpath'", messages)
