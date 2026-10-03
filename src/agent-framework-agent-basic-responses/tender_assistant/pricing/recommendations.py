"""Validate model recommendations against supplied historical candidates."""
import json


def validate_result(text, candidates):
    result = json.loads(text)

    expected = {
        "status", "rate_id", "match_basis", "reason",
        "assumptions", "differences",
    }
    if not isinstance(result, dict) or set(result) != expected:
        raise ValueError("Luna response has unexpected fields.")

    status = result["status"]
    if not isinstance(status, str) or status not in {
        "proposed_match", "needs_review", "no_suitable_candidate"
    }:
        raise ValueError("Invalid matching status.")

    if not isinstance(result["reason"], str) or not result["reason"].strip():
        raise ValueError("Matching reason is missing.")

    differences = result["differences"]
    if not isinstance(differences, list) or not all(
        isinstance(value, str) and value.strip() for value in differences
    ):
        raise ValueError("Invalid differences list.")

    assumptions = result["assumptions"]
    if not isinstance(assumptions, list) or not all(
        isinstance(value, str) and value.strip() for value in assumptions
    ):
        raise ValueError("Invalid assumptions list.")

    rate_id = result["rate_id"]
    if status == "proposed_match":
        if not isinstance(rate_id, str) or rate_id not in candidates:
            raise ValueError("Luna selected an ID outside the candidate set.")
        basis = result["match_basis"]
        if not isinstance(basis, str) or basis not in {
            "direct_description", "comparable"
        }:
            raise ValueError("Invalid match basis.")
        if basis == "comparable" and (not assumptions or not differences):
            raise ValueError("Comparable estimates require assumptions and risks.")
    elif rate_id is not None or result["match_basis"] is not None:
        raise ValueError("Unresolved matches must not select a rate or basis.")

    return result
