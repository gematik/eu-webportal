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

"""Safe evaluation of Arazzo simple Criterion Objects."""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from ..errors import ExitCode, ToolError
from .expression_evaluator import RuntimeContext, evaluate_expression_string
from .runtime_expressions import parse_runtime_expressions

_NUMBER = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?")
_COMPARISON_OPERATORS = frozenset({"==", "!=", "<", "<=", ">", ">="})


@dataclass(frozen=True)
class _Token:
    kind: str
    value: Any


def evaluate_criterion(criterion: Mapping[str, Any], context: RuntimeContext) -> bool:
    """Evaluate a supported Criterion Object without dynamic code execution."""
    criterion_type = criterion.get("type", "simple")
    if criterion_type != "simple":
        raise _criterion_error(
            f"Criterion type '{criterion_type}' is not supported by this evaluator slice."
        )
    condition = criterion.get("condition")
    if not isinstance(condition, str) or not condition.strip():
        raise _criterion_error("Criterion condition must be a non-empty string.")
    tokens = _tokenize(condition, context)
    return _Parser(tokens).parse()


def evaluate_criteria(
    criteria: Sequence[Mapping[str, Any]], context: RuntimeContext
) -> bool:
    """Evaluate criteria with Arazzo's logical AND semantics."""
    return all(evaluate_criterion(criterion, context) for criterion in criteria)


def _tokenize(condition: str, context: RuntimeContext) -> list[_Token]:
    try:
        expressions = parse_runtime_expressions(condition)
    except ValueError as error:
        raise _criterion_error(str(error)) from error
    expression_by_start = {expression.start: expression for expression in expressions}
    tokens: list[_Token] = []
    index = 0
    while index < len(condition):
        if condition[index].isspace():
            index += 1
            continue
        expression = expression_by_start.get(index)
        if expression is not None:
            if expression.embedded:
                raise _criterion_error(
                    "Simple conditions must use direct runtime expressions."
                )
            tokens.append(
                _Token("value", evaluate_expression_string(expression.value, context))
            )
            index = expression.end
            continue
        operator = next(
            (
                candidate
                for candidate in ("&&", "||", "==", "!=", "<=", ">=", "<", ">")
                if condition.startswith(candidate, index)
            ),
            None,
        )
        if operator is not None:
            tokens.append(_Token("operator", operator))
            index += len(operator)
            continue
        if condition[index] in "()":
            tokens.append(_Token(condition[index], condition[index]))
            index += 1
            continue
        if condition[index] == "'":
            literal, index = _read_string(condition, index)
            tokens.append(_Token("value", literal))
            continue
        number = _NUMBER.match(condition, index)
        if number is not None:
            tokens.append(_Token("value", Decimal(number.group())))
            index = number.end()
            continue
        keyword = next(
            (
                candidate
                for candidate in ("true", "false", "null")
                if condition.startswith(candidate, index)
            ),
            None,
        )
        if keyword is not None:
            value = {"true": True, "false": False, "null": None}[keyword]
            tokens.append(_Token("value", value))
            index += len(keyword)
            continue
        raise _criterion_error(
            f"Unexpected token at position {index} in simple condition."
        )
    if not tokens:
        raise _criterion_error("Simple condition must not be empty.")
    return tokens


def _read_string(condition: str, start: int) -> tuple[str, int]:
    result: list[str] = []
    index = start + 1
    while index < len(condition):
        if condition[index] != "'":
            result.append(condition[index])
            index += 1
            continue
        if index + 1 < len(condition) and condition[index + 1] == "'":
            result.append("'")
            index += 2
            continue
        return "".join(result), index + 1
    raise _criterion_error("String literal is missing closing quote.")


class _Parser:
    def __init__(self, tokens: list[_Token]) -> None:
        self._tokens = tokens
        self._index = 0

    def parse(self) -> bool:
        result = self._parse_or()
        if self._index != len(self._tokens):
            raise _criterion_error("Unexpected trailing tokens in simple condition.")
        return result

    def _parse_or(self) -> bool:
        result = self._parse_and()
        while self._accept_operator("||"):
            result = self._parse_and() or result
        return result

    def _parse_and(self) -> bool:
        result = self._parse_term()
        while self._accept_operator("&&"):
            result = self._parse_term() and result
        return result

    def _parse_term(self) -> bool:
        if self._accept("("):
            result = self._parse_or()
            self._require(")")
            return result
        left = self._require_value()
        operator = self._peek_operator()
        if operator in _COMPARISON_OPERATORS:
            self._index += 1
            return _compare(left, self._require_value(), operator)
        if isinstance(left, bool):
            return left
        return False

    def _require_value(self) -> Any:
        if (
            self._index >= len(self._tokens)
            or self._tokens[self._index].kind != "value"
        ):
            raise _criterion_error("Expected literal or runtime expression.")
        value = self._tokens[self._index].value
        self._index += 1
        return value

    def _peek_operator(self) -> str | None:
        if self._index >= len(self._tokens):
            return None
        token = self._tokens[self._index]
        return token.value if token.kind == "operator" else None

    def _accept_operator(self, value: str) -> bool:
        if self._peek_operator() != value:
            return False
        self._index += 1
        return True

    def _accept(self, kind: str) -> bool:
        if self._index >= len(self._tokens) or self._tokens[self._index].kind != kind:
            return False
        self._index += 1
        return True

    def _require(self, kind: str) -> None:
        if not self._accept(kind):
            raise _criterion_error(f"Expected '{kind}'.")


def _compare(left: Any, right: Any, operator: str) -> bool:
    if left is None or right is None:
        equal = left is None and right is None
        return equal if operator == "==" else not equal if operator == "!=" else False

    numeric_left = _as_decimal(left)
    numeric_right = _as_decimal(right)
    if numeric_left is not None and numeric_right is not None:
        return _ordered_compare(numeric_left, numeric_right, operator)
    if isinstance(left, str) and isinstance(right, str):
        return _ordered_compare(left.casefold(), right.casefold(), operator)
    if operator == "==":
        return type(left) is type(right) and left == right
    if operator == "!=":
        return not (type(left) is type(right) and left == right)
    return False


def _as_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal, str)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    return None


def _ordered_compare(left: Any, right: Any, operator: str) -> bool:
    comparisons: dict[str, bool] = {
        "==": left == right,
        "!=": left != right,
        "<": left < right,
        "<=": left <= right,
        ">": left > right,
        ">=": left >= right,
    }
    return comparisons[operator]


def _criterion_error(message: str) -> ToolError:
    return ToolError(
        "ARAZZO_CRITERION_EVALUATION_FAILED",
        message,
        ExitCode.TEST_ERROR,
    )
