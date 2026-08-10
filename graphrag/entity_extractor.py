from __future__ import annotations

import re
from typing import List

from .schema import Entity, normalize_entity_type


_CAPITALIZED = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b")
_YEAR = re.compile(r"\b(19\d{2}|20\d{2}|21\d{2})\b")
_NUMBER = re.compile(r"\b\d+(?:\.\d+)?\b")


_STOPWORDS = {
    "The",
    "This",
    "That",
    "These",
    "Those",
    "Court",
    "Page",
    "Section",
    "Answer",
    "Question",
}


def extract_entities(text: str) -> List[Entity]:
    entities: List[Entity] = []
    seen = set()

    for match in _CAPITALIZED.findall(text or ""):
        value = match.strip()
        if not value or value in _STOPWORDS:
            continue
        entity_type = "PERSON" if " " in value else "CONCEPT"
        key = (value.lower(), entity_type)
        if key not in seen:
            seen.add(key)
            entities.append(Entity(value=value, entity_type=normalize_entity_type(entity_type)))

    for year in _YEAR.findall(text or ""):
        key = (year, "DATE")
        if key not in seen:
            seen.add(key)
            entities.append(Entity(value=year, entity_type="DATE"))

    numeric_tokens = _NUMBER.findall(text or "")
    for token in numeric_tokens[:10]:
        key = (token, "NUMBER")
        if key not in seen:
            seen.add(key)
            entities.append(Entity(value=token, entity_type="NUMBER"))

    return entities
