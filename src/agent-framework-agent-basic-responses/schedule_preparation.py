from decimal import Decimal

from schedule_classification import classify_row
from quantity_formulas import (
    UnsupportedQuantityFormula,
    evaluate_quantity_formula,
)


def prepare_schedule(document):
    """Prepare quantities without selecting rates or calculating prices."""
    prepared = []

    for row in document["rows"]:
        classification = classify_row(row)
        fields = row["fields"]
        category = classification["category"]

        item = {
            "row_id": row["row_id"],
            "source_file": document["source_file"],
            "source_sha256": document["source_sha256"],
            "sheet": document["sheet"],
            "excel_row": row["excel_row"],
            "hidden": row["hidden"],
            "code": fields["code"]["value"],
            "description": fields["description"]["value"],
            "unit": fields["unit"]["value"],
            "quantity_original": fields["quantity"]["value"],
            "quantity_coordinate": fields["quantity"]["coordinate"],
            "quantity_resolved": None,
            "quantity_method": None,
            "category": category,
            "ready_for_rate_matching": False,
            "reason": classification["reason"],
            "source_issues": list(row["issues"]),
        }

        if category == "measured_item":
            item["quantity_resolved"] = format(
                Decimal(fields["quantity"]["value"]), "f"
            )
            item["quantity_method"] = "excel_numeric"
            item["ready_for_rate_matching"] = True

        elif category == "formula_quantity":
            try:
                quantity = evaluate_quantity_formula(
                    fields["quantity"]["value"]
                )
            except UnsupportedQuantityFormula as error:
                item["reason"] = str(error)
            else:
                item["quantity_resolved"] = format(quantity, "f")
                item["quantity_method"] = "restricted_multiplication_v1"

                unit = " ".join(
                    str(item["unit"]).split()
                ).casefold()

                if unit in {"ls", "l.s.", "lump sum", "sum", "item"}:
                    item["reason"] = (
                        "Quantity resolved; lump-sum/item pricing "
                        "still requires a separate rule."
                    )
                else:
                    item["ready_for_rate_matching"] = True
                    item["reason"] = (
                        "Formula quantity resolved; "
                        "rate compatibility still required."
                    )

        # Hidden rows are retained, but not automatically progressed.
        if item["hidden"]:
            item["ready_for_rate_matching"] = False
            item["reason"] = (
                "Hidden source row; confirm whether it belongs "
                "in the pricing scope."
            )

        prepared.append(item)

    return prepared