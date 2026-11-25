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
from typing import Any

import yaml

from tools.openapi_arazzo_tool.errors import ExitCode, ToolError
from tools.openapi_arazzo_tool.openapi.refs import resolve_ref

FIXTURES = Path(__file__).parent / "fixtures" / "openapi" / "refs"
ALLOWED_ROOT = str(FIXTURES / "src")


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        document = yaml.safe_load(stream)
    if not isinstance(document, dict):
        raise AssertionError(f"Expected mapping in {path}.")
    return document


class ResolveRefTest(unittest.TestCase):
    def test_resolves_deeply_nested_relative_ref_without_flattening(self) -> None:
        service_path = (
            FIXTURES / "src" / "interfaces" / "service" / "nested" / "service.yaml"
        )
        document = _load(service_path)
        ref = document["components"]["schemas"]["WidgetRef"]["$ref"]

        result = resolve_ref(document, str(service_path), ref, [ALLOWED_ROOT])

        self.assertEqual(
            result.file_path, (FIXTURES / "src" / "domain" / "schemas.yaml").resolve()
        )
        self.assertEqual(
            result.value, {"type": "object", "properties": {"id": {"type": "string"}}}
        )

    def test_resolves_internal_fragment_only_ref_without_file_access(self) -> None:
        self_ref_path = (
            FIXTURES / "src" / "interfaces" / "service" / "nested" / "self-ref.yaml"
        )
        document = _load(self_ref_path)
        ref = document["components"]["schemas"]["WidgetAlias"]["$ref"]

        result = resolve_ref(document, str(self_ref_path), ref, [ALLOWED_ROOT])

        self.assertEqual(result.file_path, self_ref_path)
        self.assertEqual(result.value, {"type": "object"})

    def test_rejects_ref_escaping_allowed_root(self) -> None:
        service_path = (
            FIXTURES / "src" / "interfaces" / "service" / "nested" / "service.yaml"
        )
        document = _load(service_path)
        ref = "../../../../outside/escape-target.yaml#/components/schemas/Forbidden"

        with self.assertRaises(ToolError) as context:
            resolve_ref(document, str(service_path), ref, [ALLOWED_ROOT])
        self.assertEqual(context.exception.code, "OPENAPI_REF_FORBIDDEN")
        self.assertEqual(context.exception.exit_code, ExitCode.VALIDATION_ERROR)

    def test_rejects_absolute_path_ref(self) -> None:
        service_path = (
            FIXTURES / "src" / "interfaces" / "service" / "nested" / "service.yaml"
        )
        document = _load(service_path)
        absolute_target = str((FIXTURES / "src" / "domain" / "schemas.yaml").resolve())
        ref = f"{absolute_target}#/components/schemas/Widget"

        with self.assertRaises(ToolError) as context:
            resolve_ref(document, str(service_path), ref, [ALLOWED_ROOT])
        self.assertEqual(context.exception.code, "OPENAPI_REF_FORBIDDEN")

    def test_rejects_remote_ref(self) -> None:
        service_path = (
            FIXTURES / "src" / "interfaces" / "service" / "nested" / "service.yaml"
        )
        document = _load(service_path)
        ref = "https://example.org/schemas.yaml#/components/schemas/Widget"

        with self.assertRaises(ToolError) as context:
            resolve_ref(document, str(service_path), ref, [ALLOWED_ROOT])
        self.assertEqual(context.exception.code, "OPENAPI_REF_FORBIDDEN")

    def test_rejects_missing_target_file(self) -> None:
        service_path = (
            FIXTURES / "src" / "interfaces" / "service" / "nested" / "service.yaml"
        )
        document = _load(service_path)
        ref = "../../../domain/does-not-exist.yaml#/components/schemas/Widget"

        with self.assertRaises(ToolError) as context:
            resolve_ref(document, str(service_path), ref, [ALLOWED_ROOT])
        self.assertEqual(context.exception.code, "OPENAPI_REF_UNRESOLVED")

    def test_rejects_unresolvable_fragment(self) -> None:
        service_path = (
            FIXTURES / "src" / "interfaces" / "service" / "nested" / "service.yaml"
        )
        document = _load(service_path)
        ref = "../../../domain/schemas.yaml#/components/schemas/DoesNotExist"

        with self.assertRaises(ToolError) as context:
            resolve_ref(document, str(service_path), ref, [ALLOWED_ROOT])
        self.assertEqual(context.exception.code, "OPENAPI_REF_UNRESOLVED")

    def test_rejects_symlink_escaping_allowed_root(self) -> None:
        link_path = FIXTURES / "src" / "domain" / "escaped-symlink.yaml"
        target_path = FIXTURES / "outside" / "escape-target.yaml"
        try:
            link_path.symlink_to(target_path)
        except OSError as error:
            self.skipTest(
                f"Symlink creation not permitted in this environment: {error}"
            )

        try:
            service_path = (
                FIXTURES / "src" / "interfaces" / "service" / "nested" / "service.yaml"
            )
            document = _load(service_path)
            ref = "../../../domain/escaped-symlink.yaml#/components/schemas/Forbidden"

            with self.assertRaises(ToolError) as context:
                resolve_ref(document, str(service_path), ref, [ALLOWED_ROOT])
            self.assertEqual(context.exception.code, "OPENAPI_REF_FORBIDDEN")
        finally:
            link_path.unlink()
