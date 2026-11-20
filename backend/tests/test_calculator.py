"""
Unit tests for the safe mathematical calculator tool.
"""

import pytest
from app.tools.calculator import calculate


def test_basic_arithmetic():
    assert calculate("125 * 48") == "6000"
    assert calculate("1000 / 8") == "125"
    assert calculate("10 + 20 - 5") == "25"
    assert calculate("7 * 8") == "56"


def test_parentheses():
    assert calculate("(25 * 4) + 100") == "200"
    assert calculate("25 * (4 + 100)") == "2600"
    assert calculate("((10 + 5) * 2) / 6") == "5"


def test_percentages():
    assert calculate("15% of 50000") == "7500"
    assert calculate("15% * 50000") == "7500"
    assert calculate("15% of 50,000") == "7500"
    assert calculate("100 + 15%") == "100.15"


def test_powers():
    assert calculate("2 ^ 8") == "256"
    assert calculate("2 ** 8") == "256"
    assert calculate("(3 + 1) ^ 2") == "16"


def test_division_by_zero():
    res = calculate("100 / 0")
    assert "Error" in res
    assert "Division by zero" in res


def test_safety_rejection():
    # Attempt code execution or imports
    res1 = calculate("__import__('os').system('dir')")
    assert "Error" in res1

    res2 = calculate("eval('2 + 2')")
    assert "Error" in res2

    res3 = calculate("open('/etc/passwd')")
    assert "Error" in res3


def test_empty_or_invalid():
    assert "Error" in calculate("")
    assert "Error" in calculate("   ")
    assert "Error" in calculate("abc + 12")
