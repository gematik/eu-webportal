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

"""Tests for deterministic sample values of constrained strings."""

import re
import unittest

from tools.openapi_arazzo_tool.mocking.patterns import format_value, pattern_value

SUPPORTED = [
    ("^[A-Z]{2}$", "AA"),
    ("[0-9]{3}-[0-9]{2}", "000-00"),
    ("^abc$", "abc"),
    ("^a?b+c*$", "b"),
    ("^(foo|bar)$", "foo"),
    ("^(?:x){2}$", "xx"),
    (r"^\d{4}-\d{2}$", "0000-00"),
    ("^[a-z0-9_]+$", "a"),
    ("^.{2}$", "xx"),
    (r"^a\.b$", "a.b"),
    ("^[A-Z]{1,3}$", "A"),
]

UNSUPPORTED = [
    "^[^a]$",
    r"^(a)\1$",
    "^(?=a)a$",
    "^a{2,1}$",
    "^)$",
    "^a{x}$",
    "",
]


class PatternValueTest(unittest.TestCase):
    def test_returns_shortest_matching_value(self) -> None:
        for pattern, expected in SUPPORTED:
            with self.subTest(pattern=pattern):
                value = pattern_value(pattern)
                self.assertEqual(value, expected)
                if value is None:
                    self.fail("Supported pattern did not produce a value.")
                self.assertIsNotNone(re.search(pattern, value))

    def test_rejects_unsupported_patterns(self) -> None:
        for pattern in UNSUPPORTED:
            with self.subTest(pattern=pattern):
                self.assertIsNone(pattern_value(pattern))

    def test_rejects_non_string_pattern(self) -> None:
        self.assertIsNone(pattern_value(42))

    def test_is_deterministic(self) -> None:
        self.assertEqual(pattern_value("^[A-Z]{4}$"), pattern_value("^[A-Z]{4}$"))


class FormatValueTest(unittest.TestCase):
    def test_returns_canonical_samples(self) -> None:
        self.assertEqual(format_value("uuid"), "00000000-0000-4000-8000-000000000000")
        self.assertEqual(format_value("date"), "2024-01-01")
        self.assertEqual(format_value("uri"), "https://example.org/mock")

    def test_returns_none_for_unknown_format(self) -> None:
        self.assertIsNone(format_value("jwt"))
        self.assertIsNone(format_value(None))


if __name__ == "__main__":
    unittest.main()
