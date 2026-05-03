from __future__ import annotations


STAR_PREFIX = "\u2605 "

COLLECTIBLE_PREFIXES = (
    "Bayonet |",
    "Bowie Knife |",
    "Butterfly Knife |",
    "Classic Knife |",
    "Falchion Knife |",
    "Flip Knife |",
    "Gut Knife |",
    "Huntsman Knife |",
    "Karambit |",
    "Kukri Knife |",
    "M9 Bayonet |",
    "Navaja Knife |",
    "Nomad Knife |",
    "Paracord Knife |",
    "Shadow Daggers |",
    "Skeleton Knife |",
    "Stiletto Knife |",
    "Survival Knife |",
    "Talon Knife |",
    "Ursus Knife |",
    "Bloodhound Gloves |",
    "Broken Fang Gloves |",
    "Driver Gloves |",
    "Hand Wraps |",
    "Hydra Gloves |",
    "Moto Gloves |",
    "Specialist Gloves |",
    "Sport Gloves |",
)


def market_hash_candidates(item_name: str) -> list[str]:
    normalized = item_name.strip()
    if not normalized:
        return []
    if normalized.startswith(STAR_PREFIX):
        return [normalized]
    if any(normalized.startswith(prefix) for prefix in COLLECTIBLE_PREFIXES):
        return [normalized, f"{STAR_PREFIX}{normalized}"]
    return [normalized]
