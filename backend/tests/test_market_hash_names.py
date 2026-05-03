from app.services.market_hash_names import market_hash_candidates


def test_glove_market_hash_candidates_include_starred_name() -> None:
    assert market_hash_candidates("Sport Gloves | Scarlet Shamagh (Field-Tested)") == [
        "Sport Gloves | Scarlet Shamagh (Field-Tested)",
        "\u2605 Sport Gloves | Scarlet Shamagh (Field-Tested)",
    ]


def test_weapon_market_hash_candidates_keep_plain_name() -> None:
    assert market_hash_candidates("AK-47 | Redline (Field-Tested)") == [
        "AK-47 | Redline (Field-Tested)",
    ]
