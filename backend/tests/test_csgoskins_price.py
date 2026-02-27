from app.services.csgoskins_price import extract_active_offer_prices, extract_product_metadata


def test_extract_product_metadata_reads_product_ld_json() -> None:
    html = '''
    <script type="application/ld+json">{
      "@context": "https://schema.org",
      "@type": "Product",
      "name": "AK-47 | Redline",
      "image": ["https://cdn.example.com/ak-redline.png"],
      "offers": {
        "@type": "AggregateOffer",
        "lowPrice": "29.30",
        "highPrice": "352.60"
      }
    }</script>
    '''

    low, high, image = extract_product_metadata(html)
    assert low == 29.30
    assert high == 352.60
    assert image == "https://cdn.example.com/ak-redline.png"


def test_extract_active_offer_prices_maps_markets_and_uses_lowest_duplicate() -> None:
    html = '''
    <div class="active-offer bg-gray-800">
      <a class="custom-underline" href="https://csgoskins.gg/markets/csmoney">
        <img src="x" alt="">CS.MONEY
      </a>
      <div class="w-full text-gray-400">from</div>
      <div class="w-full font-bold text-lg sm:text-xl">$1,520.00</div>
    </div>
    <div class="active-offer bg-gray-800">
      <a class="custom-underline" href="https://csgoskins.gg/markets/csmoney">
        <img src="x" alt="">CS.MONEY
      </a>
      <div class="w-full text-gray-400">from</div>
      <div class="w-full font-bold text-lg sm:text-xl">$1,499.99</div>
    </div>
    <div class="active-offer bg-gray-800">
      <a class="custom-underline" href="https://csgoskins.gg/markets/buff163">
        <img src="x" alt="">BUFF163
      </a>
      <div class="w-full text-gray-400">from</div>
      <div class="w-full font-bold text-lg sm:text-xl">$1,488.40</div>
    </div>
    '''

    prices = extract_active_offer_prices(html)
    assert prices["csmoney"] == 1499.99
    assert prices["buff163"] == 1488.40
