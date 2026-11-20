"""
Safe Mathematical Calculator Tool for Multi-Agent AI System.

Evaluates mathematical expressions without using unrestricted eval().
Supports:
- Addition (+)
- Subtraction (-)
- Multiplication (*)
- Division (/)
- Percentages (e.g., '15% of 50000', '15% * 50000', '100 + 15%')
- Powers (^ and **)
- Parentheses ((...))
"""

import ast
import logging
import operator
import re
from typing import Any, Union

logger = logging.getLogger(__name__)

# Supported safe AST operators mapped to standard operator functions
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# Maximum allowed power exponent to prevent denial-of-service
MAX_EXPONENT = 1000
MAX_BASE = 100000


def _evaluate_ast_node(node: ast.AST) -> Union[int, float]:
    """
    Recursively evaluate an AST expression node using only whitelisted operators.

    Args:
        node (ast.AST): AST node to evaluate.

    Returns:
        Union[int, float]: Numerical result.

    Raises:
        ZeroDivisionError: If division by zero is attempted.
        ValueError: If unsupported syntax, operator, or out-of-bounds power is found.
    """
    if isinstance(node, ast.Expression):
        return _evaluate_ast_node(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant type: {type(node.value).__name__}")

    if isinstance(node, ast.UnaryOp):
        operand = _evaluate_ast_node(node.operand)
        op_type = type(node.op)
        if op_type in SAFE_OPERATORS:
            return SAFE_OPERATORS[op_type](operand)
        raise ValueError(f"Unsupported unary operator: {op_type.__name__}")

    if isinstance(node, ast.BinOp):
        left = _evaluate_ast_node(node.left)
        right = _evaluate_ast_node(node.right)
        op_type = type(node.op)

        if op_type not in SAFE_OPERATORS:
            raise ValueError(f"Unsupported binary operator: {op_type.__name__}")

        if op_type == ast.Div and right == 0:
            raise ZeroDivisionError("Division by zero is not allowed.")

        if op_type == ast.Pow:
            if abs(left) > MAX_BASE or abs(right) > MAX_EXPONENT:
                raise ValueError("Exponent or base is too large to evaluate safely.")

        return SAFE_OPERATORS[op_type](left, right)

    raise ValueError(f"Unsupported syntax construct: {type(node).__name__}")


def preprocess_expression(expr: str) -> str:
    """
    Sanitize and preprocess natural mathematical syntax before AST parsing.

    Transformations:
    - Removes currency/unit symbols (e.g. $, EUR).
    - Removes thousand-separator commas within numbers (e.g., 50,000 -> 50000).
    - Normalizes '^' to '**'.
    - Converts 'X% of Y' to '(X / 100) * Y'.
    - Converts 'X%' to '(X / 100)'.
    """
    cleaned = expr.strip()

    # Remove currency symbols
    cleaned = re.sub(r"[\$€£₹]", "", cleaned)

    # Remove commas between digits (e.g. 50,000 -> 50000)
    cleaned = re.sub(r"(\d+),(\d+)", r"\1\2", cleaned)

    # Convert "X% of Y" to "(X / 100) * Y" (case-insensitive)
    cleaned = re.sub(
        r"(\d+(?:\.\d+)?)\s*%\s+of\s+",
        r"(\1 / 100) * ",
        cleaned,
        flags=re.IGNORECASE,
    )

    # Convert standalone "X%" to "(X / 100)"
    cleaned = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"(\1 / 100)", cleaned)

    # Convert '^' power operator to '**'
    cleaned = cleaned.replace("^", "**")

    return cleaned


def calculate(expression: str) -> str:
    """
    Safely evaluate a mathematical expression string.

    Args:
        expression (str): Expression to evaluate, e.g. '125 * 48', '15% of 50000', '(25 * 4) + 100'.

    Returns:
        str: String representation of the calculated numerical result.
    """
    logger.info("Calculator received expression: '%s'", expression)

    if not expression or not expression.strip():
        return "Error: Expression cannot be empty."

    try:
        preprocessed = preprocess_expression(expression)
        parsed_ast = ast.parse(preprocessed, mode="eval")
        result = _evaluate_ast_node(parsed_ast)

        # Format integer results cleanly (e.g. 6000.0 -> 6000)
        if isinstance(result, float) and result.is_integer():
            formatted_result = str(int(result))
        elif isinstance(result, float):
            formatted_result = f"{result:.6g}"
        else:
            formatted_result = str(result)

        logger.info("Calculator successfully evaluated '%s' = %s", expression, formatted_result)
        return formatted_result

    except ZeroDivisionError:
        logger.warning("Calculator error: Division by zero in '%s'", expression)
        return "Error: Division by zero is undefined."
    except SyntaxError as err:
        logger.warning("Calculator syntax error in '%s': %s", expression, str(err))
        return f"Error: Invalid mathematical syntax ('{expression}')."
    except Exception as err:
        logger.warning("Calculator evaluation error in '%s': %s", expression, str(err))
        return f"Error: {str(err)}"
