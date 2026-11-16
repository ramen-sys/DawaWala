"""Expand class-level interaction rules into medication pairs (FR-8, BR-05).

A curated rule such as "warfarin x NSAID" is written once and turned into one
ordinary pair rule per NSAID. The same function runs in two places, so both
always agree:

  * loader.load_kb()          - against the medications in the curated CSVs
  * scripts.import_kb_rules   - against every medication in the database,
                                including the Kaggle ones (e.g. celecoxib)

Precedence, most specific first:
  1. a rule written for the exact pair always wins;
  2. medication x class beats class x class;
  3. two rules of the same specificity covering one pair is a curation error,
     because the knowledge base cannot say which severity is right.

Members are left out of a class when:
  * they are local products (creams, eye drops, oral gels), which do not carry
    systemic interactions (see models.is_local_product);
  * one of their active ingredients is itself a member of the same side. For
    "Ibuprofen + Pseudoephedrine" the engine already applies ibuprofen's rule
    through the ingredient, so expanding the combination as well would give the
    patient the same warning twice.
"""

from __future__ import annotations

from typing import Iterable, Mapping

from .models import (
    ClassInteractionRule,
    InteractionRule,
    Medication,
    expanded_rule_id,
    is_local_product,
)


def class_members(
    medication_id: int | None,
    drug_class: str | None,
    medications: Mapping[int, Medication],
    components: Mapping[int, tuple[int, ...]],
) -> list[int]:
    """Medication ids one side of a class rule applies to, in id order."""
    if medication_id is not None:
        return [medication_id]
    members = {
        med.medication_id
        for med in medications.values()
        if drug_class in med.classes and not is_local_product(med.standard_name)
    }
    return sorted(m for m in members if not members.intersection(components.get(m, ())))


def expand_class_interactions(
    rules: Iterable[ClassInteractionRule],
    medications: Mapping[int, Medication],
    components: Mapping[int, tuple[int, ...]],
    explicit_pairs: Iterable[tuple[int, int]],
) -> tuple[list[InteractionRule], list[str]]:
    """Return (generated pair rules, errors).

    explicit_pairs are the (low, high) pairs that already have a rule of their own.
    Generated ids look like "INT-0100/5-12" and carry parent_rule_id "INT-0100".
    """
    taken = {tuple(sorted(pair)) for pair in explicit_pairs}
    claimed: dict[tuple[int, int], ClassInteractionRule] = {}
    generated: list[InteractionRule] = []
    errors: list[str] = []

    for rule in sorted(rules, key=lambda r: (-r.specificity, r.rule_id)):
        side_a = class_members(rule.a_medication, rule.a_class, medications, components)
        side_b = class_members(rule.b_medication, rule.b_class, medications, components)
        for a in side_a:
            for b in side_b:
                if a == b:
                    continue
                pair = (a, b) if a < b else (b, a)
                if pair in taken:
                    continue
                other = claimed.get(pair)
                if other is not None:
                    if other.specificity == rule.specificity and other.rule_id != rule.rule_id:
                        names = " + ".join(medications[m].standard_name for m in pair)
                        errors.append(
                            f"interactions: rules {other.rule_id} and {rule.rule_id} both cover {names}; "
                            "add a rule for that exact pair or narrow one of them"
                        )
                    continue
                claimed[pair] = rule
                generated.append(
                    InteractionRule(
                        expanded_rule_id(rule.rule_id, *pair), pair[0], pair[1], rule.severity,
                        rule.description, rule.relevant_factors, rule.source, parent_rule_id=rule.rule_id,
                    )
                )

    generated.sort(key=lambda r: r.rule_id)
    return generated, errors
