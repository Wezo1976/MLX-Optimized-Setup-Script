from __future__ import annotations

from dataclasses import dataclass

VALID_ENTITY_TYPES = {"PERSON", "ORG", "PLACE", "CONCEPT", "DATE", "NUMBER"}


@dataclass(frozen=True)
class Entity:
    value: str
    entity_type: str


@dataclass(frozen=True)
class Relation:
    source: str
    target: str
    relation_type: str


def normalize_entity_type(entity_type: str) -> str:
    upper = (entity_type or "CONCEPT").upper()
    return upper if upper in VALID_ENTITY_TYPES else "CONCEPT"


def valid_relation_type(relation_type: str) -> str:
    clean = (relation_type or "related_to").strip().lower()
    return clean if clean else "related_to"
