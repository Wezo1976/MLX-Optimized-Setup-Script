from __future__ import annotations

import re
from itertools import combinations
from typing import List

from .schema import Relation, valid_relation_type


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def extract_relations(text: str, entity_values: List[str]) -> List[Relation]:
    relations: List[Relation] = []
    if not text or len(entity_values) < 2:
        return relations

    values_set = {v for v in entity_values if v}
    for sentence in _SENTENCE_SPLIT.split(text):
        present = [v for v in values_set if v in sentence]
        if len(present) < 2:
            continue
        for source, target in combinations(sorted(set(present)), 2):
            relations.append(
                Relation(
                    source=source,
                    target=target,
                    relation_type=valid_relation_type("co_occurs_in_sentence"),
                )
            )

    return relations
