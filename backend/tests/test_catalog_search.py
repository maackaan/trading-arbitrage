from app.services.catalog_search import build_display_name, extract_wears_from_html, infer_default_wears


def test_extract_wears_orders_standard_exteriors() -> None:
    html = '''
    <a class="version-link" href="https://csgoskins.gg/items/ak-47-redline/minimal-wear">MW</a>
    <a class="version-link" href="https://csgoskins.gg/items/ak-47-redline/factory-new">FN</a>
    <a class="version-link" href="https://csgoskins.gg/items/ak-47-redline/battle-scarred">BS</a>
    <a class="version-link" href="https://csgoskins.gg/items/ak-47-redline/well-worn">WW</a>
    <a class="version-link" href="https://csgoskins.gg/items/ak-47-redline/field-tested">FT</a>
    '''
    assert extract_wears_from_html(html) == [
        "Factory New",
        "Minimal Wear",
        "Field-Tested",
        "Well-Worn",
        "Battle-Scarred",
    ]


def test_extract_wears_supports_stattrak_prefix() -> None:
    html = '<a class="version-link" href="https://csgoskins.gg/items/m9-bayonet-doppler/stattrak-minimal-wear">x</a>'
    assert extract_wears_from_html(html) == ["Minimal Wear"]


def test_build_display_name_prefixes_category() -> None:
    assert build_display_name("Tiger Tooth", "Talon Knife") == "Talon Knife | Tiger Tooth"
    assert build_display_name("AK-47 | Redline", "AK-47") == "AK-47 | Redline"


def test_infer_default_wears_handles_vanilla() -> None:
    assert infer_default_wears("https://csgoskins.gg/items/karambit-vanilla") == ["Vanilla"]
