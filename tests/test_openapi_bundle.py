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

"""Tests for bundling cross-file references into a single document."""

import unittest
from pathlib import Path

import yaml

from tools.openapi_arazzo_tool.errors import ToolError
from tools.openapi_arazzo_tool.openapi.bundle import BUNDLE_CONTAINER, bundle_document
from tools.openapi_arazzo_tool.openapi.model import OpenApiDocument

FIXTURES = Path(__file__).parent / "fixtures" / "openapi" / "refs"
ALLOWED_ROOT = str(FIXTURES / "src")


def _document(path: Path) -> OpenApiDocument:
    with path.open(encoding="utf-8") as stream:
        return OpenApiDocument(
            path=str(path), version="3.1.0", raw=yaml.safe_load(stream)
        )


class BundleDocumentTest(unittest.TestCase):
    def test_hoists_external_ref_and_rewrites_pointer(self) -> None:
        source = _document(
            FIXTURES / "src" / "interfaces" / "service" / "nested" / "service.yaml"
        )

        bundled = bundle_document(source, [ALLOWED_ROOT])

        ref = bundled.raw["components"]["schemas"]["WidgetRef"]["$ref"]
        self.assertTrue(ref.startswith(f"#/components/{BUNDLE_CONTAINER}/"))
        name = ref.rsplit("/", 1)[1]
        self.assertEqual(
            bundled.raw["components"][BUNDLE_CONTAINER][name],
            {"type": "object", "properties": {"id": {"type": "string"}}},
        )

    def test_keeps_document_local_refs_untouched(self) -> None:
        path = FIXTURES / "src" / "interfaces" / "service" / "nested" / "self-ref.yaml"
        source = _document(path)

        bundled = bundle_document(source, [ALLOWED_ROOT])

        self.assertEqual(
            bundled.raw["components"]["schemas"]["WidgetAlias"]["$ref"],
            source.raw["components"]["schemas"]["WidgetAlias"]["$ref"],
        )
        self.assertNotIn(BUNDLE_CONTAINER, bundled.raw.get("components", {}))

    def test_does_not_mutate_source_document(self) -> None:
        path = FIXTURES / "src" / "interfaces" / "service" / "nested" / "service.yaml"
        source = _document(path)
        original = yaml.safe_load(yaml.safe_dump(source.raw))

        bundle_document(source, [ALLOWED_ROOT])

        self.assertEqual(source.raw, original)

    def test_is_deterministic(self) -> None:
        path = FIXTURES / "src" / "interfaces" / "service" / "nested" / "service.yaml"

        first = bundle_document(_document(path), [ALLOWED_ROOT]).raw
        second = bundle_document(_document(path), [ALLOWED_ROOT]).raw

        self.assertEqual(first, second)
        self.assertEqual(
            list(first["components"][BUNDLE_CONTAINER]),
            list(second["components"][BUNDLE_CONTAINER]),
        )

    def test_rejects_ref_outside_allowed_roots(self) -> None:
        path = FIXTURES / "src" / "interfaces" / "service" / "nested" / "service.yaml"
        source = _document(path)
        source.raw["components"]["schemas"]["Escape"] = {
            "$ref": "../../../../outside/escape-target.yaml#/components/schemas/Forbidden"
        }

        with self.assertRaises(ToolError) as context:
            bundle_document(source, [ALLOWED_ROOT])

        self.assertEqual(context.exception.code, "OPENAPI_REF_FORBIDDEN")


class BundleRecursionTest(unittest.TestCase):
    def test_terminates_on_recursive_external_schema(
        self,
    ) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "domain.yaml").write_text(
                yaml.safe_dump(
                    {
                        "components": {
                            "schemas": {
                                "Node": {
                                    "type": "object",
                                    "properties": {
                                        "child": {"$ref": "#/components/schemas/Node"}
                                    },
                                }
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            service = root / "service.yaml"
            service.write_text(
                yaml.safe_dump(
                    {
                        "components": {
                            "schemas": {
                                "Root": {"$ref": "domain.yaml#/components/schemas/Node"}
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            bundled = bundle_document(_document(service), [str(root)])

            fragments = bundled.raw["components"][BUNDLE_CONTAINER]
            self.assertEqual(len(fragments), 1)
            name = next(iter(fragments))
            self.assertEqual(
                fragments[name]["properties"]["child"]["$ref"],
                f"#/components/{BUNDLE_CONTAINER}/{name}",
            )


if __name__ == "__main__":
    unittest.main()
