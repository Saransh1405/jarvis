import pytest

from jarvis_ai.tools.calculator import CalculatorError, evaluate_expression


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("2+2", "4"),
        ("99*101", "9999"),
        ("15*0.2", "3"),
        ("(10+5)/3", "5"),
        ("-3+10", "7"),
        ("2**8", "256"),
    ],
)
def test_evaluate_expression(expression: str, expected: str) -> None:
    assert evaluate_expression(expression) == expected


def test_evaluate_empty_expression() -> None:
    with pytest.raises(CalculatorError, match="empty"):
        evaluate_expression("   ")


def test_evaluate_rejects_unsafe_syntax() -> None:
    with pytest.raises(CalculatorError):
        evaluate_expression("__import__('os').system('ls')")

    with pytest.raises(CalculatorError):
        evaluate_expression("abs(-1)")
