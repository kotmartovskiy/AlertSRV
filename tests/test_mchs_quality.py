from urllib.error import HTTPError

from alertsrv.adapters.mchs_rss import MchsRssAdapter
from alertsrv.poller import SourceFetchResult


def test_mchs_fallback_is_marked_degraded(monkeypatch):
    adapter = MchsRssAdapter(
        rss_url="https://37.mchs.gov.ru/regional/rss",
        general_fallback_url="https://37.mchs.gov.ru/general/rss",
    )

    def fake_fetch(url):
        if url.endswith("regional/rss"):
            raise HTTPError(url, 404, "missing", {}, None)
        from xml.etree import ElementTree
        root = ElementTree.Element("rss")
        channel = ElementTree.SubElement(root, "channel")
        item = ElementTree.SubElement(channel, "item")
        ElementTree.SubElement(item, "title").text = "Storm warning"
        ElementTree.SubElement(item, "pubDate").text = "Sun, 04 Oct 26 12:12:00 +0300"
        ElementTree.SubElement(item, "link").text = "https://37.mchs.gov.ru/x/1"
        return root

    monkeypatch.setattr(adapter, "_fetch_root", fake_fetch)
    result = adapter.fetch()
    assert isinstance(result, SourceFetchResult)
    assert result.parser_degraded is True
    assert result.events
    assert "fallback" in (result.detail or "")
