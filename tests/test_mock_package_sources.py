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

import contextlib
import io
import json
import shutil
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from tools.openapi_arazzo_tool.cli import _generate_mocks
from tools.openapi_arazzo_tool.errors import ToolError
from tools.openapi_arazzo_tool.mocking.package import load_mock_package
from tools.openapi_arazzo_tool.mocking.sources import (
    PackageSources,
    collect_package_sources,
)

API = """openapi: 3.1.0
info:
  title: Source collection
  version: 1.0.0
paths:
  /ready:
    get:
      operationId: ready
      responses:
        '200':
          description: Ready
          content:
            text/plain:
              schema:
                type: string
              example: ready
"""


class MockPackageSourcesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = Path.cwd() / f".mock-package-sources-{uuid.uuid4().hex}"
        self.root = self.workspace / "definitions"
        self.root.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.workspace)

    def write(self, name: str, content: str) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode("utf-8"))
        return path.resolve()

    def collect(
        self, openapi: list[Path], arazzo: list[Path] | None = None
    ) -> PackageSources:
        return collect_package_sources(openapi, arazzo or [], [str(self.root)])

    def test_collects_nested_and_cyclic_refs_without_scanning_directories(self) -> None:
        api = self.write(
            "api.yaml",
            API
            + "components:\n  schemas:\n    Node:\n      $ref: schemas/node.yaml#/Node\n",
        )
        node = self.write(
            "schemas/node.yaml",
            "Node:\n  type: object\n  properties:\n    child:\n"
            "      $ref: ../shared/child.yaml#/Child\n"
            "Unused:\n  $ref: ../unrelated.yaml#/Unused\n",
        )
        child = self.write(
            "shared/child.yaml",
            "Child:\n  type: object\n  properties:\n    parent:\n"
            "      $ref: ../schemas/node.yaml#/Node\n",
        )
        self.write("credentials.yaml", "secret: must-not-export\n")
        self.write("unrelated.yaml", "Unused:\n  type: string\n")

        sources = self.collect([api])

        self.assertEqual(sources.openapi, (api, node, child))
        self.assertEqual(sources.arazzo, ())
        self.assertEqual(len(sources.references), 3)
        self.assertEqual(sources.references[-1].target_index, 2)
        self.assertEqual(sources, self.collect([api]))

    def test_keeps_configured_roots_first_and_deduplicates_canonical_paths(
        self,
    ) -> None:
        first = self.write(
            "first.yaml",
            API + "components:\n  schemas:\n    Value:\n      $ref: value.yaml\n",
        )
        second = self.write("second.yaml", API)
        dependency = self.write("value.yaml", "type: string\n")

        sources = self.collect([first, second, first.parent / "." / first.name])

        self.assertEqual(sources.openapi, (first, second, dependency))

    def test_traverses_distinct_fragments_and_ref_siblings(self) -> None:
        api = self.write(
            "api.yaml",
            API + "components:\n  schemas:\n"
            "    First:\n      $ref: shared.yaml#/First\n"
            "      properties:\n        sibling:\n          $ref: sibling.json\n"
            "    Second:\n      $ref: shared.yaml#/Second\n",
        )
        shared = self.write(
            "shared.yaml",
            "First:\n  type: string\nSecond:\n  $ref: nested.yaml#/Nested\n",
        )
        sibling = self.write("sibling.json", '{"type": "integer"}\n')
        nested = self.write("nested.yaml", "Nested:\n  type: string\n")

        sources = self.collect([api])

        self.assertEqual(sources.openapi, (api, shared, sibling, nested))
        self.assertEqual(len(sources.references), 4)

    def test_same_basename_dependencies_have_distinct_portable_relationships(
        self,
    ) -> None:
        api = self.write(
            "api.yaml",
            API + "components:\n  schemas:\n"
            "    First:\n      $ref: first/common.yaml\n"
            "    Second:\n      $ref: second/common.yaml\n",
        )
        first = self.write("first/common.yaml", "type: string\n")
        second = self.write("second/common.yaml", "type: integer\n")

        sources = self.collect([api])
        provenance = sources.provenance()

        self.assertEqual(sources.openapi, (api, first, second))
        self.assertEqual([item["target"]["index"] for item in provenance], [2, 3])
        self.assertEqual(
            [item["reference"] for item in provenance],
            ["first/common.yaml", "second/common.yaml"],
        )
        self.assertNotIn(str(self.workspace), json.dumps(provenance))
        self.assertEqual(provenance[0]["location"], "/components/schemas/First/$ref")

    def test_collects_arazzo_source_not_in_configured_openapi_roots(self) -> None:
        api = self.write("api.yaml", API)
        source = self.write(
            "other/service.yaml",
            API + "components:\n  schemas:\n    Value:\n      $ref: value.yaml\n",
        )
        dependency = self.write("other/value.yaml", "type: string\n")
        workflow = self.write(
            "workflow.yaml",
            "arazzo: 1.1.0\nsourceDescriptions:\n"
            "  - name: service\n    type: openapi\n    url: other/service.yaml\n",
        )

        sources = self.collect([api], [workflow])

        self.assertEqual(sources.openapi, (api, source, dependency))
        self.assertEqual(sources.arazzo, (workflow,))
        self.assertEqual(
            sources.provenance()[0],
            {
                "source": {"kind": "arazzo", "index": 1},
                "target": {"kind": "openapi", "index": 2},
                "reference": "other/service.yaml",
                "location": "/sourceDescriptions/0/url",
            },
        )

    def test_rejects_forbidden_transitive_refs(self) -> None:
        outside = self.workspace / "outside.yaml"
        outside.write_text("type: string\n", encoding="utf-8")
        api = self.write(
            "api.yaml",
            API + "components:\n  schemas:\n    Value:\n      $ref: value.yaml\n",
        )
        for ref in (
            "../outside.yaml",
            "https://example.invalid/schema.yaml",
            "file:///schema.yaml",
        ):
            with self.subTest(ref=ref):
                self.write("value.yaml", f"$ref: {ref}\n")
                with self.assertRaises(ToolError) as raised:
                    self.collect([api])
                self.assertEqual(raised.exception.code, "OPENAPI_REF_FORBIDDEN")

    def test_rejects_forbidden_arazzo_source_descriptions(self) -> None:
        api = self.write("api.yaml", API)
        outside = self.workspace / "outside.yaml"
        outside.write_text(API, encoding="utf-8")
        for url in ("../outside.yaml", "https://example.invalid/api.yaml"):
            with self.subTest(url=url):
                workflow = self.write(
                    "workflow.yaml",
                    "arazzo: 1.1.0\nsourceDescriptions:\n"
                    f"  - name: external\n    type: openapi\n    url: {url}\n",
                )
                with self.assertRaises(ToolError) as raised:
                    self.collect([api], [workflow])
                self.assertEqual(raised.exception.code, "ARAZZO_SOURCE_FORBIDDEN")

    def test_rejects_missing_or_invalid_reference_targets(self) -> None:
        api = self.write(
            "api.yaml",
            API
            + "components:\n  schemas:\n    Value:\n      $ref: missing.yaml#/Value\n",
        )
        with self.assertRaises(ToolError) as raised:
            self.collect([api])
        self.assertEqual(raised.exception.code, "OPENAPI_REF_UNRESOLVED")

        self.write("missing.yaml", "Other:\n  type: string\n")
        with self.assertRaises(ToolError) as raised:
            self.collect([api])
        self.assertEqual(raised.exception.code, "OPENAPI_REF_UNRESOLVED")

        self.write("missing.yaml", "Value: [\n")
        with self.assertRaises(ToolError) as raised:
            self.collect([api])
        self.assertEqual(raised.exception.code, "OPENAPI_REF_UNRESOLVED")

    def test_package_copies_original_bytes_and_loads_after_source_root_removal(
        self,
    ) -> None:
        api = self.write(
            "api.yaml",
            API
            + "components:\n  schemas:\n    Value:\n      $ref: nested/value.yaml\n",
        )
        dependency = self.write(
            "nested/value.yaml", "# Preserve comment and CRLF\r\ntype: string\r\n"
        )
        original_bytes = (api.read_bytes(), dependency.read_bytes())
        output = self.workspace / "package"
        config = {
            "openapi": [str(api)],
            "security": {"allowedRefRoots": [str(self.root)]},
            "mock": {"packageVersion": "1.0.0"},
        }
        with patch(
            "tools.openapi_arazzo_tool.cli.generator_version", return_value="1.0.0"
        ):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(_generate_mocks(config, str(output)), 0)
        self.assertEqual(
            (output / "sources" / "openapi" / "0001-api.yaml").read_bytes(),
            original_bytes[0],
        )
        self.assertEqual(
            (output / "sources" / "openapi" / "0002-value.yaml").read_bytes(),
            original_bytes[1],
        )
        shutil.rmtree(self.root)

        with patch(
            "yaml.safe_load", side_effect=AssertionError("Sources must not be parsed")
        ):
            manifest, routes = load_mock_package(output)

        self.assertEqual(manifest["packageVersion"], "1.0.0")
        self.assertEqual(routes[0].response.body, b"ready")


if __name__ == "__main__":
    unittest.main()
