from alertsrv.adapters.mchs_catalog import MchsRegion, MchsRegionalCatalog


def test_catalog_parser_fixture():
    from alertsrv.adapters.mchs_catalog import _SiteParser
    p = _SiteParser()
    p.feed('<a href="https://37.mchs.gov.ru/">Ivanovo</a><a href="https://40.mchs.gov.ru/">Kaluga</a><a href="https://example.org/">x</a>')
    assert p.urls == {"https://37.mchs.gov.ru", "https://40.mchs.gov.ru"}
    p = _SiteParser()
    p.feed('<a href="https://moscow.mchs.gov.ru">Moscow</a>')
    assert "https://moscow.mchs.gov.ru" in p.urls


def test_region_rss_url():
    assert MchsRegion("37", "https://37.mchs.gov.ru").rss_url.endswith("/rss")


def test_live_catalog_smoke():
    import os
    if os.getenv("ALERTSRV_LIVE_MCHS") != "1":
        return
    regions = MchsRegionalCatalog().discover()
    assert len(regions) >= 80
    assert any(r.code == "37" for r in regions)
