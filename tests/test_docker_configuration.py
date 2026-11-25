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

import yaml


class DockerConfigurationTest(unittest.TestCase):
    def test_compose_keeps_spec_inputs_read_only_and_no_exposed_ports(self) -> None:
        root = Path(__file__).resolve().parents[1]
        compose = yaml.safe_load(
            (root / "docker-compose.yml").read_text(encoding="utf-8")
        )
        service = compose["services"]["tool"]
        self.assertTrue(service["read_only"])
        self.assertNotIn("ports", service)
        self.assertTrue(service["user"].startswith("10001:"))
        self.assertIn("/tmp", service["tmpfs"])
        self.assertTrue(
            all(
                volume.endswith(":ro")
                for volume in service["volumes"]
                if "/workspace/reports" not in volume
            )
        )

    def test_dockerfile_runs_unprivileged(self) -> None:
        root = Path(__file__).resolve().parents[1]
        dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("USER tool", dockerfile)
        self.assertIn("install -y --no-install-recommends git", dockerfile)
        self.assertIn("tools.openapi_arazzo_tool.cli", dockerfile)

    def test_versioned_mock_image_contains_package_and_does_not_publish_ports(
        self,
    ) -> None:
        root = Path(__file__).resolve().parents[1]
        dockerfile = (root / "Dockerfile.mock").read_text(encoding="utf-8")
        justfile = (root / "justfile").read_text(encoding="utf-8")
        dockerignore = (root / ".dockerignore").read_text(encoding="utf-8")
        self.assertIn("COPY ${MOCK_PACKAGE_DIR}/ /opt/mock-package/", dockerfile)
        self.assertIn("manifest['packageVersion']", dockerfile)
        self.assertIn(
            'CMD ["start-mocks", "--package-dir", "/opt/mock-package"]', dockerfile
        )
        self.assertIn("USER tool", dockerfile)
        self.assertNotIn("EXPOSE ", dockerfile)
        self.assertIn("docker-build-mock package_dir version:", justfile)
        self.assertIn("node_modules", dockerignore)
        self.assertNotIn("dist", dockerignore)
