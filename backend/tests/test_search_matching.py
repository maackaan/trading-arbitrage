from app.services.search_matching import score_skin_name, suggest_skin_names


def test_ak47_alias_matches_hyphenated_skin_name() -> None:
    score = score_skin_name("ak47", "AK-47 | Redline (Field-Tested)")
    assert score > 120.0


def test_knives_query_matches_knife_item() -> None:
    score = score_skin_name("knives", "Butterfly Knife | Doppler (Factory New)")
    assert score > 80.0


def test_suggest_skin_names_returns_best_candidates() -> None:
    names = [
        "AK-47 | Redline (Field-Tested)",
        "Desert Eagle | Blaze (Factory New)",
        "Karambit | Doppler (Factory New)",
    ]
    suggestions = suggest_skin_names("deagle", names)
    assert suggestions
    assert suggestions[0] == "Desert Eagle | Blaze (Factory New)"
