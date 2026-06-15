"""
engines/research_agent/tools/calculator_tool.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CalculatorTool — safe arithmetic evaluator for numeric UPSC queries.

Examples of queries this handles:
  - "What is 15% of India's GDP if GDP is $3.5 trillion?"
  - "Calculate per capita income: 180 lakh crore / 140 crore population"
  - "Growth rate: (current - previous) / previous * 100"

Security: uses ast.parse() whitelist approach — NEVER eval() or exec().
Only allows: numbers, +, -, *, /, **, (, ), %, unary minus.
Any other token → rejected with clear error message.
"""

from __future__ import annotations

import ast
import operator
from typing import Callable
import structlog
import sentry_sdk

logger = structlog.get_logger(__name__)

# Whitelist of allowed AST node types
_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
)

# Binary operators — take two float arguments
_BINARY_OPS: dict[type, Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# Unary operators — take one float argument
_UNARY_OPS: dict[type, Callable[[float], float]] = {
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

MAX_EXPRESSION_LENGTH = 200
MAX_RESULT_MAGNITUDE = 1e18  # reject astronomically large results


class CalculatorError(Exception):
    """Raised when expression is invalid or unsafe."""

    pass


class CalculatorTool:
    """
    Safe arithmetic evaluator.

    The Research Agent calls this when the query contains numeric/percentage
    calculations (detected by Planner Agent domain classification).

    Returns a formatted string result, not a raw float — ready to inject
    directly into the research context without further formatting.
    """

    def calculate(self, expression: str) -> str:
        """
        Safely evaluate an arithmetic expression.

        Args:
            expression: Arithmetic string e.g. "3.5e12 * 0.15"

        Returns:
            Formatted result string e.g. "525000000000.0"

        Raises:
            CalculatorError: If expression is unsafe, invalid, or too complex.
        """
        try:
            expression = expression.strip()

            if len(expression) > MAX_EXPRESSION_LENGTH:
                raise CalculatorError(
                    f"Expression too long ({len(expression)} chars). Max {MAX_EXPRESSION_LENGTH}."
                )

            if not expression:
                raise CalculatorError("Empty expression.")

            result = self._safe_eval(expression)

            if abs(result) > MAX_RESULT_MAGNITUDE:
                raise CalculatorError(
                    f"Result magnitude too large: {result}. Possible infinite loop or overflow."
                )

            # Format: strip unnecessary trailing zeros for clean output
            if isinstance(result, float) and result.is_integer():
                formatted = str(int(result))
            else:
                formatted = f"{result:.6g}"

            logger.info(
                "research_agent.calculator.evaluated",
                expression=expression,
                result=formatted,
            )

            return formatted

        except CalculatorError:
            raise
        except ZeroDivisionError:
            raise CalculatorError("Division by zero.")
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise CalculatorError(f"Calculation failed: {exc}") from exc

    def _safe_eval(self, expression: str) -> float:
        """
        Parse expression into AST, validate all nodes against whitelist,
        then walk the tree to compute the result.

        This approach is safe because:
          - ast.parse() never executes code
          - We validate every node type before touching it
          - No builtins, no attributes, no function calls are allowed
        """
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise CalculatorError(f"Invalid expression syntax: {exc}") from exc

        # Validate every node in the tree
        for node in ast.walk(tree):
            if not isinstance(node, _ALLOWED_NODES):
                raise CalculatorError(
                    f"Unsafe operation in expression: {type(node).__name__}. "
                    "Only basic arithmetic is allowed."
                )

        return self._eval_node(tree.body)

    def _eval_node(self, node: ast.expr) -> float:
        """Recursively evaluate a validated AST node."""
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)):
                raise CalculatorError(f"Non-numeric constant: {node.value!r}")
            return float(node.value)

        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            bin_fn = _BINARY_OPS.get(type(node.op))
            if bin_fn is None:
                raise CalculatorError(f"Unsupported operator: {type(node.op).__name__}")
            return bin_fn(left, right)

        if isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            unary_fn = _UNARY_OPS.get(type(node.op))
            if unary_fn is None:
                raise CalculatorError(
                    f"Unsupported unary operator: {type(node.op).__name__}"
                )
            return unary_fn(operand)

        raise CalculatorError(f"Unexpected node type: {type(node).__name__}")
