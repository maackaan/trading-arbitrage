from __future__ import annotations

import re

WEAR_ORDER = {
    "Factory New": 0,
    "Minimal Wear": 1,
    "Field-Tested": 2,
    "Well-Worn": 3,
    "Battle-Scarred": 4,
    "Vanilla": 5,
}

WEAR_SUFFIX_RE = re.compile(
    r"^(?P<base>.+) \((?P<wear>Factory New|Minimal Wear|Field-Tested|Well-Worn|Battle-Scarred|Vanilla)\)$"
)

PREFERRED_LISTING_WEAR = [
    "Field-Tested",
    "Minimal Wear",
    "Factory New",
    "Well-Worn",
    "Battle-Scarred",
]


def split_wear_suffix(name: str) -> tuple[str, str | None]:
    match = WEAR_SUFFIX_RE.match(name.strip())
    if not match:
        return name.strip(), None
    return match.group("base"), match.group("wear")


def has_wear_suffix(name: str) -> bool:
    return split_wear_suffix(name)[1] is not None
