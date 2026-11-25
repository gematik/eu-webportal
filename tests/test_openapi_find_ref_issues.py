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
from tools.openapi_arazzo_tool.openapi.refs import find_ref_issues

FIXTURES = Path(__file__).parent / "fixtures" / "openapi" / "refs"


class FindRefIssuesTest(unittest.TestCase):
    def test_resolves_multi_file_chain_without_issues(self) -> None:
        document = load_openapi_document(str(FIXTURES / "chain" / "root.yaml"))
        issues = find_ref_issues(document, [str(FIXTURES / "chain")])
        self.assertEqual(issues, [])

    def test_reports_unresolved_ref_nested_two_files_deep(self) -> None:
        document = load_openapi_document(str(FIXTURES / "chain" / "root-broken.yaml"))
        issues = find_ref_issues(document, [str(FIXTURES / "chain")])

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].code, "OPENAPI_REF_UNRESOLVED")
        self.assertIn("does-not-exist.yaml", issues[0].message)

    def test_cross_file_cycle_resolves_without_infinite_loop(self) -> None:
        document = load_openapi_document(str(FIXTURES / "cycle" / "node-a.yaml"))
        issues = find_ref_issues(document, [str(FIXTURES / "cycle")])
        self.assertEqual(issues, [])

    def test_self_referencing_schema_resolves_without_infinite_loop(self) -> None:
        document = load_openapi_document(str(FIXTURES / "cycle" / "self-cycle.yaml"))
        issues = find_ref_issues(document, [str(FIXTURES / "cycle")])
        self.assertEqual(issues, [])

    def test_reports_forbidden_ref_escaping_allowed_root(self) -> None:
        document = load_openapi_document(
            str(FIXTURES / "src" / "interfaces" / "service" / "nested" / "service.yaml")
        )
        # Allow only the interfaces subtree, deliberately excluding "domain",
        # so the cross-directory ref used by this fixture must be rejected.
        narrow_root = str(FIXTURES / "src" / "interfaces")
        issues = find_ref_issues(document, [narrow_root])

        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].code, "OPENAPI_REF_FORBIDDEN")

    def test_reports_json_path_location_of_failing_ref(self) -> None:
        document = load_openapi_document(str(FIXTURES / "chain" / "root-broken.yaml"))
        issues = find_ref_issues(document, [str(FIXTURES / "chain")])

        self.assertIn("found at", issues[0].message)
