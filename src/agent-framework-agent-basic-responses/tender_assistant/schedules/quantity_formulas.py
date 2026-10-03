import re
from decimal import Decimal, localcontext


class UnsupportedQuantityFormula(ValueError):
    pass


# Only non-negative decimal numbers joined by multiplication.
_NUMBER = r"[0-9]+(?:\.[0-9]+)?"
_MULTIPLICATION = re.compile(
    rf"{_NUMBER}(?:\s*\*\s*{_NUMBER})*"
)


def evaluate_quantity_formula(formula: str) -> Decimal:
    """Evaluate a restricted numeric multiplication formula exactly."""
    if not isinstance(formula, str):
        raise UnsupportedQuantityFormula("Formula must be text.")

    expression = formula.strip()

    if len(expression) > 1000:
        raise UnsupportedQuantityFormula("Formula is too long.")

    if not expression.startswith("="):
        raise UnsupportedQuantityFormula("Formula must start with '='.")

    expression = expression[1:].strip()

    if not _MULTIPLICATION.fullmatch(expression):
        raise UnsupportedQuantityFormula(
            "Only non-negative decimal numbers joined by '*' "
            "are supported. Cell references and functions "
            "require separate handling."
        )

    factors = [
        Decimal(part.strip())
        for part in expression.split("*")
    ]

    # Sufficient precision for the exact product of all factors.
    precision = max(
        28,
        sum(len(factor.as_tuple().digits) for factor in factors),
    )

    with localcontext() as context:
        context.prec = precision
        result = Decimal("1")
        for factor in factors:
            result *= factor

    return result
