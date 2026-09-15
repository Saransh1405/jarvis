"""Safe calculator tool — evaluates basic math expressions."""

import ast
import operator
from typing import Any

from jarvis_ai.policy.policy import Tier
from jarvis_ai.tools.base import Tool

_BINARY_OPS: dict[type[ast.operator], Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

_UNARY_OPS: dict[type[ast.unaryop], Any] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


class CalculatorError(ValueError):
    """Raised when an expression cannot be evaluated safely."""


def evaluate_expression(expression: str) -> str:
    """
    Evaluate a math expression using AST only (no eval(), no function calls).

    Supports integers, floats, + - * / // % ** and parentheses.
    """
    expr = expression.strip()
    if not expr:
        raise CalculatorError("expression is empty")

    try:
        node = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise CalculatorError(f"invalid expression: {exc.msg}") from exc

    result = _eval_node(node.body)
    if isinstance(result, float) and result.is_integer():
        return str(int(result))
    return str(result)


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise CalculatorError("only numbers are allowed")

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BINARY_OPS:
            raise CalculatorError(f"unsupported operator: {op_type.__name__}")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        if op_type is ast.Div and right == 0:
            raise CalculatorError("division by zero")
        if op_type is ast.FloorDiv and right == 0:
            raise CalculatorError("division by zero")
        if op_type is ast.Mod and right == 0:
            raise CalculatorError("division by zero")
        return float(_BINARY_OPS[op_type](left, right))

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise CalculatorError(f"unsupported operator: {op_type.__name__}")
        return float(_UNARY_OPS[op_type](_eval_node(node.operand)))

    raise CalculatorError(f"unsupported syntax: {type(node).__name__}")


def _run_calculator(args: dict[str, Any]) -> str:
    expression = args.get("expression")
    if not isinstance(expression, str) or not expression.strip():
        return "Error: 'expression' must be a non-empty string"
    try:
        return evaluate_expression(expression)
    except CalculatorError as exc:
        return f"Error: {exc}"


def calculator_tool() -> Tool:
    return Tool(
        name="calculator",
        description=(
            "Evaluate a math expression. Use for arithmetic like addition, "
            "multiplication, percentages, and parentheses."
        ),
        tier=Tier.SAFE,
        parameters={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Math expression, e.g. '2+2', '15*0.2', '(10+5)/3'",
                }
            },
            "required": ["expression"],
        },
        run=_run_calculator,
    )
