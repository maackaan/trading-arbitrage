from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable

ALIAS_BY_TOKEN = {
    "ak47": "ak-47",
    "m4a1s": "m4a1-s",
    "m4a1": "m4a1-s",
    "deagle": "desert eagle",
    "usp": "usp-s",
    "usps": "usp-s",
    "glock": "glock-18",
    "scout": "ssg 08",
    "bfk": "butterfly knife",
    "bayo": "bayonet",
    "m9": "m9 bayonet",
    "knives": "knife",
    "knifes": "knife",
}

ALIAS_BY_QUERY = {
    "ak47": "ak-47",
    "m4a1s": "m4a1-s",
    "deagle": "desert eagle",
    "usp": "usp-s",
    "usps": "usp-s",
    "bfk": "butterfly knife",
    "knives": "knife",
    "knifes": "knife",
}


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower())


def expand_query_variants(query: str) -> set[str]:
    lowered = query.strip().lower()
    normalized = normalize_text(lowered)
    variants = {lowered}

    if normalized in ALIAS_BY_QUERY:
        variants.add(ALIAS_BY_QUERY[normalized])

    tokens = tokenize(lowered)
    expanded_tokens = [ALIAS_BY_TOKEN.get(token, token) for token in tokens]
    if expanded_tokens:
        variants.add(" ".join(expanded_tokens))

    if "knife" in expanded_tokens:
        variants.update(
            {
                "karambit",
                "bayonet",
                "m9 bayonet",
                "butterfly knife",
                "falchion knife",
            }
        )

    return {variant.strip() for variant in variants if variant.strip()}


def score_skin_name(query: str, skin_name: str) -> float:
    query_lower = query.strip().lower()
    if not query_lower:
        return 0.0

    name_lower = skin_name.lower()
    query_norm = normalize_text(query_lower)
    name_norm = normalize_text(name_lower)

    variants = expand_query_variants(query_lower)

    score = 0.0

    if query_lower in name_lower:
        score += 120.0
    if query_norm and query_norm in name_norm:
        score += 160.0

    for variant in variants:
        variant_norm = normalize_text(variant)
        if variant in name_lower:
            score += 70.0
        if variant_norm and variant_norm in name_norm:
            score += 95.0

    query_tokens = set(tokenize(" ".join(variants)))
    name_tokens = set(tokenize(name_lower))

    if query_tokens:
        overlap = len(query_tokens.intersection(name_tokens)) / len(query_tokens)
        score += overlap * 65.0

    if query_norm:
        ratio = SequenceMatcher(None, query_norm, name_norm).ratio()
        score += ratio * 35.0

    if query_tokens and name_tokens and query_tokens.issubset(name_tokens):
        score += 45.0

    return score


def suggest_skin_names(query: str, skin_names: Iterable[str], limit: int = 5) -> list[str]:
    scored = sorted(
        ((score_skin_name(query, name), name) for name in skin_names),
        key=lambda pair: pair[0],
        reverse=True,
    )
    return [name for score, name in scored if score >= 35.0][:limit]
