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
from tools.openapi_arazzo_tool.http.bodies import serialize_request_body


class HttpBodySerializationTest(unittest.TestCase):
    def test_serializes_json_deterministically_as_utf8(self) -> None:
        result = serialize_request_body(
            {"name": "Wïdget", "active": True},
            "application/json",
        )

        self.assertEqual(result.content_type, "application/json")
        self.assertEqual(result.data, '{"name":"Wïdget","active":true}'.encode())

    def test_serializes_form_values_with_property_encoding(self) -> None:
        result = serialize_request_body(
            {
                "tag": ["red", "blue"],
                "filter": {"state": "ready", "next": "/widgets?page=2"},
            },
            "application/x-www-form-urlencoded",
            {
                "tag": {"explode": False},
                "filter": {"explode": True, "allowReserved": True},
            },
        )

        self.assertEqual(
            result.data,
            b"tag=red,blue&state=ready&next=/widgets?page=2",
        )

    def test_serializes_multipart_json_text_binary_and_arrays(self) -> None:
        result = serialize_request_body(
            {
                "metadata": {"name": "Widget"},
                "note": "hello",
                "file": b"\x00\x01",
                "tag": ["red", "blue"],
            },
            "multipart/form-data",
            {"metadata": {"contentType": "application/json"}},
            multipart_boundary="test-boundary",
        )

        self.assertEqual(
            result.content_type, "multipart/form-data; boundary=test-boundary"
        )
        self.assertIn(b'Content-Disposition: form-data; name="metadata"', result.data)
        self.assertIn(
            b'Content-Type: application/json\r\n\r\n{"name":"Widget"}', result.data
        )
        self.assertIn(
            b"Content-Type: application/octet-stream\r\n\r\n\x00\x01", result.data
        )
        self.assertEqual(result.data.count(b'name="tag"'), 2)
        self.assertTrue(result.data.endswith(b"--test-boundary--\r\n"))

    def test_serializes_binary_text_and_xml(self) -> None:
        binary = serialize_request_body(
            memoryview(b"\x01\x02"), "application/octet-stream"
        )
        text = serialize_request_body("hello", "text/plain; charset=utf-8")
        xml = serialize_request_body("<root/>", "application/xml")

        self.assertEqual(binary.data, b"\x01\x02")
        self.assertEqual(text.data, b"hello")
        self.assertEqual(xml.data, b"<root/>")

    def test_rejects_unsupported_media_invalid_payload_and_boundary_collision(
        self,
    ) -> None:
        with self.assertRaises(ToolError) as unsupported:
            serialize_request_body({}, "application/cbor")
        with self.assertRaises(ToolError) as invalid_binary:
            serialize_request_body("not-bytes", "application/octet-stream")
        with self.assertRaises(ToolError) as collision:
            serialize_request_body(
                {"file": b"contains-test-boundary"},
                "multipart/form-data",
                multipart_boundary="test-boundary",
            )

        self.assertEqual(unsupported.exception.code, "HTTP_BODY_SERIALIZATION_FAILED")
        self.assertEqual(unsupported.exception.exit_code, ExitCode.TEST_ERROR)
        self.assertEqual(
            invalid_binary.exception.code, "HTTP_BODY_SERIALIZATION_FAILED"
        )
        self.assertIn("collides", collision.exception.message)

    def test_rejects_multipart_header_injection(self) -> None:
        with self.assertRaises(ToolError) as context:
            serialize_request_body(
                {"bad\r\nInjected": "value"},
                "multipart/form-data",
            )

        self.assertIn("CR or LF", context.exception.message)
