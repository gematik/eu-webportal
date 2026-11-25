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

"""Deterministic sample values for constrained string schemas.

Real specifications constrain strings with ``format`` and ``pattern``. A mock
that ignores those constraints produces responses that violate its own
contract, so both are honored here. Pattern support covers a documented subset
of regular expressions; anything outside that subset returns ``None`` so the
caller can fail explicitly instead of emitting an invalid value.
"""

from __future__ import annotations

from typing import Any

_MAX_REPEAT = 64

_FORMAT_VALUES: dict[str, str] = {
    "date": "2024-01-01",
    "date-time": "2024-01-01T00:00:00Z",
    "duration": "PT1S",
    "email": "mock@example.org",
    "hostname": "example.org",
    "idn-email": "mock@example.org",
    "idn-hostname": "example.org",
    "ipv4": "192.0.2.1",
    "ipv6": "2001:db8::1",
    "iri": "https://example.org/mock",
    "iri-reference": "/mock",
    "json-pointer": "/mock",
    "regex": "^mock$",
    "relative-json-pointer": "0/mock",
    "time": "00:00:00Z",
    "uri": "https://example.org/mock",
    "uri-reference": "/mock",
    "uri-template": "/mock/{id}",
    "url": "https://example.org/mock",
    "uuid": "00000000-0000-4000-8000-000000000000",
}

_CLASS_SHORTHAND: dict[str, str] = {
    "d": "0",
    "w": "a",
    "s": " ",
    "D": "a",
    "W": "-",
    "S": "a",
}


def format_value(schema_format: Any) -> str | None:
    """Return a canonical sample value for a known string ``format``."""
    if not isinstance(schema_format, str):
        return None
    return _FORMAT_VALUES.get(schema_format)


def pattern_value(pattern: Any) -> str | None:
    """Return the shortest deterministic string matching ``pattern``.

    Supported: anchors, literals, ``.``, escapes, character classes with
    ranges, groups, alternation (first branch wins) and the quantifiers
    ``?``, ``*``, ``+`` and ``{n}`` / ``{n,m}``. Returns ``None`` for anything
    else, including backreferences, lookarounds and negated classes.
    """
    if not isinstance(pattern, str) or not pattern:
        return None
    parser = _PatternParser(pattern)
    try:
        value = parser.parse_alternation()
    except _UnsupportedPattern:
        return None
    if not parser.at_end():
        return None
    return value


class _UnsupportedPattern(Exception):
    pass


class _PatternParser:
    """Recursive-descent parser producing the shortest matching string."""

    def __init__(self, pattern: str) -> None:
        self._pattern = pattern
        self._index = 0

    def at_end(self) -> bool:
        return self._index >= len(self._pattern)

    def parse_alternation(self) -> str:
        value = self.parse_sequence()
        while self._peek() == "|":
            self._index += 1
            # Only the first branch is materialized, but the remaining
            # branches must still be well-formed to be accepted.
            self.parse_sequence()
        return value

    def parse_sequence(self) -> str:
        parts: list[str] = []
        while (char := self._peek()) is not None and char not in "|)":
            parts.append(self._parse_quantified())
        return "".join(parts)

    def _parse_quantified(self) -> str:
        atom = self._parse_atom()
        minimum, maximum = self._parse_quantifier()
        if maximum is not None and maximum < minimum:
            raise _UnsupportedPattern
        if minimum > _MAX_REPEAT:
            raise _UnsupportedPattern
        return atom * minimum

    def _parse_atom(self) -> str:
        char = self._peek()
        if char is None:
            raise _UnsupportedPattern
        if char in "^$":
            self._index += 1
            return ""
        if char == "(":
            return self._parse_group()
        if char == "[":
            return self._parse_class()
        if char == "\\":
            return self._parse_escape()
        if char == ".":
            self._index += 1
            return "x"
        if char in "*+?{}|)":
            raise _UnsupportedPattern
        self._index += 1
        return char

    def _parse_group(self) -> str:
        self._index += 1
        if self._pattern.startswith("?", self._index):
            if not self._pattern.startswith("?:", self._index):
                raise _UnsupportedPattern
            self._index += 2
        value = self.parse_alternation()
        if self._peek() != ")":
            raise _UnsupportedPattern
        self._index += 1
        return value

    def _parse_class(self) -> str:
        self._index += 1
        if self._peek() == "^":
            raise _UnsupportedPattern
        first: str | None = None
        while (char := self._peek()) != "]":
            if char is None:
                raise _UnsupportedPattern
            if char == "\\":
                candidate = self._parse_escape()
            else:
                self._index += 1
                candidate = char
                if self._peek() == "-" and self._pattern[
                    self._index + 1 : self._index + 2
                ] not in ("]", ""):
                    self._index += 1
                    end = self._peek()
                    if end is None or end == "\\":
                        raise _UnsupportedPattern
                    self._index += 1
                    if ord(end) < ord(candidate):
                        raise _UnsupportedPattern
            if first is None:
                first = candidate
        self._index += 1
        if first is None:
            raise _UnsupportedPattern
        return first

    def _parse_escape(self) -> str:
        self._index += 1
        char = self._peek()
        if char is None:
            raise _UnsupportedPattern
        self._index += 1
        if char.isdigit():
            raise _UnsupportedPattern
        if char in _CLASS_SHORTHAND:
            return _CLASS_SHORTHAND[char]
        if char in "AbBZz":
            raise _UnsupportedPattern
        if char == "n":
            return "\n"
        if char == "t":
            return "\t"
        if char == "r":
            return "\r"
        if char.isalnum():
            raise _UnsupportedPattern
        return char

    def _parse_quantifier(self) -> tuple[int, int | None]:
        char = self._peek()
        if char == "?":
            self._index += 1
            self._skip_lazy()
            return 0, 1
        if char == "*":
            self._index += 1
            self._skip_lazy()
            return 0, None
        if char == "+":
            self._index += 1
            self._skip_lazy()
            return 1, None
        if char == "{":
            return self._parse_repeat()
        return 1, 1

    def _parse_repeat(self) -> tuple[int, int | None]:
        closing = self._pattern.find("}", self._index)
        if closing == -1:
            raise _UnsupportedPattern
        body = self._pattern[self._index + 1 : closing]
        self._index = closing + 1
        self._skip_lazy()
        low, separator, high = body.partition(",")
        if not low.isdigit():
            raise _UnsupportedPattern
        minimum = int(low)
        if not separator:
            return minimum, minimum
        if high == "":
            return minimum, None
        if not high.isdigit():
            raise _UnsupportedPattern
        return minimum, int(high)

    def _skip_lazy(self) -> None:
        if self._peek() == "?":
            self._index += 1

    def _peek(self) -> str | None:
        if self.at_end():
            return None
        return self._pattern[self._index]
