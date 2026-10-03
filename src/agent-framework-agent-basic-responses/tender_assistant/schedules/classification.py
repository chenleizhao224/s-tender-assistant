from decimal import Decimal, InvalidOperation


def normalize(value):
    if value is None:
        return ""
    return " ".join(str(value).split()).casefold()


def classify_row(row):
    """Classify a source row without modifying it."""
    fields = row["fields"]
    quantity_field = fields["quantity"]

    quantity = normalize(quantity_field["value"])
    unit = normalize(fields["unit"]["value"])
    description = normalize(fields["description"]["value"])
    code = normalize(fields["code"]["value"])

    def result(category, reason):
        return {
            "row_id": row["row_id"],
            "excel_row": row["excel_row"],
            "category": category,
            "reason": reason,
        }

    # Explicit markers take precedence over ordinary numeric checks.
    if quantity == "note":
        return result(
            "note",
            "Scope or pricing instruction; retain for interpretation.",
        )

    if quantity in {"incl.", "incl", "included"}:
        return result(
            "included",
            "Marked included; retain without creating a separate amount.",
        )

    if quantity == "rate only" or (
        not quantity and "rate only" in description
    ):
        return result(
            "rate_only",
            "Rate requested without an extended quantity amount.",
        )

    if not quantity and not unit:
        if description or code:
            return result(
                "heading_or_note",
                "No quantity or unit; retain as contextual information.",
            )
        return result("blank", "No item content.")

    if not description:
        return result(
            "needs_review",
            "Description is missing.",
        )

    if not unit:
        return result(
            "needs_review",
            "Unit is missing.",
        )

    if unit == "%":
        return result(
            "percentage",
            "Requires an explicit percentage and calculation base.",
        )

    if not quantity:
        return result(
            "needs_review",
            "Quantity is missing; do not assume zero or one.",
        )

    if quantity_field["data_type"] == "f":
        return result(
            "formula_quantity",
            "Formula retained; requires supported formula evaluation.",
        )

    if quantity_field["data_type"] != "n":
        return result(
            "needs_review",
            "Quantity is text or another non-numeric cell type.",
        )

    try:
        number = Decimal(quantity)
    except InvalidOperation:
        return result("needs_review", "Quantity cannot be parsed.")

    if not number.is_finite():
        return result("needs_review", "Quantity is not finite.")

    if number < 0:
        return result(
            "needs_review",
            "Negative quantity requires confirmation.",
        )

    if unit in {"ls", "l.s.", "lump sum", "sum", "item"}:
        return result(
            "lump_sum_or_item",
            "Requires a separate lump-sum or item pricing rule.",
        )

    return result(
        "measured_item",
        "Numeric quantity and unit present; rate compatibility still required.",
    )


def classify_schedule(document):
    return [classify_row(row) for row in document["rows"]]
