import json

import pytest

from parsers import (parse_edpb, parse_eurlex, parse_federal_register,
                     parse_ftc, parse_uk_legislation)

RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel><title>News</title><link>https://example.test/</link>
<description>News</description><item><title>Privacy guidance</title>
<link>https://example.test/privacy</link><pubDate>Tue, 20 Oct 2026 09:00:00 GMT</pubDate>
<description>&lt;p&gt;Protect &amp;amp; secure personal data.&lt;/p&gt;</description>
</item></channel></rss>"""
ATOM = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>New legislation</title>
<id>urn:legislation</id><updated>2026-10-20T09:00:00Z</updated><entry>
<id>urn:act:1</id><title>Data Protection Act</title>
<link rel="self" href="https://example.test/data.xml" type="application/atom+xml"/>
<link rel="alternate" href="https://example.test/act" type="text/html"/>
<updated>2026-10-20T09:00:00Z</updated><summary>Privacy legislation</summary>
</entry></feed>"""


@pytest.mark.parametrize("parser", [parse_eurlex, parse_edpb])
def test_rss_adapters(parser):
    item, = parser(RSS, "test_source", "https://example.test/feed")
    assert item.source == "test_source"
    assert item.title == "Privacy guidance"
    assert item.url == "https://example.test/privacy"
    assert item.published == "2026-10-20T09:00:00+00:00"
    assert item.summary == "Protect & secure personal data."


def test_atom_alternate_link_and_updated_fallback():
    item, = parse_uk_legislation(ATOM, "uk_legislation", "https://example.test/feed")
    assert item.url == "https://example.test/act"
    assert item.published == "2026-10-20T09:00:00+00:00"
    assert item.summary == "Privacy legislation"


def test_federal_register_json():
    body = json.dumps({"results": [{"title": "Privacy rule", "html_url": "https://example.test/rule",
                                   "publication_date": "2026-10-20", "abstract": None}]}).encode()
    item, = parse_federal_register(body, "federal_register", "https://example.test/api")
    assert item.source == "federal_register"
    assert item.title == "Privacy rule"
    assert item.url == "https://example.test/rule"
    assert item.published == "2026-10-20"
    assert item.summary == ""


def test_reject_html_challenge():
    with pytest.raises(ValueError):
        parse_edpb(b"<html><body>Access challenge</body></html>", "edpb", "https://example.test")


@pytest.mark.xfail(strict=True, raises=NotImplementedError,
                   reason="TODO learning exercise: implement parse_ftc, then remove this marker")
def test_ftc_expected_rss_contract():
    """Expected failure until the user implements the FTC RSS adapter."""
    item, = parse_ftc(RSS, "ftc", "https://www.ftc.gov/feed")
    assert item.source == "ftc"
    assert item.title == "Privacy guidance"
    assert item.url == "https://example.test/privacy"
    assert item.published == "2026-10-20T09:00:00+00:00"
    assert item.summary == "Protect & secure personal data."
