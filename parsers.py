"""Four working adapters and one deliberately unfinished learning exercise."""
import calendar
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from urllib.parse import urljoin, urlsplit

import feedparser

from models import Item


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain_text(value):
    parser = PlainText()
    parser.feed(value or "")
    return " ".join(" ".join(parser.parts).split())


def valid_url(value):
    return urlsplit(value).scheme in {"https", "http"} and bool(urlsplit(value).netloc)


def parse_feed(body, source, base_url):
    feed = feedparser.parse(body)
    if not feed.version or (feed.bozo and not feed.entries):
        raise ValueError(f"{source}: response is not a usable RSS/Atom feed")
    items = []
    for entry in feed.entries:
        title = plain_text(entry.get("title", ""))
        links = [link.get("href", "") for link in entry.get("links", [])
                 if link.get("rel", "alternate") == "alternate"]
        link = entry.get("link") or next(iter(links), "")
        url = urljoin(base_url, link) if link else ""
        if not title or not valid_url(url):
            raise ValueError(f"{source}: entry has no title or HTTP link")
        timestamp = entry.get("published_parsed") or entry.get("updated_parsed")
        published = (datetime.fromtimestamp(calendar.timegm(timestamp), timezone.utc)
                     .isoformat() if timestamp else None)
        content = entry.get("content", [{}])[0].get("value", "")
        summary = plain_text(entry.get("summary") or content)
        items.append(Item(source, title, url, published, summary))
    return items


def parse_eurlex(body, source, base_url):
    return parse_feed(body, source, base_url)


def parse_edpb(body, source, base_url):
    return parse_feed(body, source, base_url)


def parse_uk_legislation(body, source, base_url):
    return parse_feed(body, source, base_url)


def parse_federal_register(body, source, base_url):
    payload = json.loads(body)
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise ValueError("Federal Register response has no results array")
    items = []
    for record in payload["results"]:
        title = plain_text(record.get("title"))
        url = record.get("html_url", "")
        if not title or not valid_url(url):
            raise ValueError("Federal Register record has no title or HTTP link")
        items.append(Item(source, title, url, record.get("publication_date"),
                          plain_text(record.get("abstract"))))
    return items


def parse_ftc(body, source, base_url):
    # TODO (learning exercise): parse consumer-protection RSS into list[Item].
    # Preserve source, title, link, publication date and plain-text description.
    # Reuse parse_feed above; tests/test_parsers.py documents the contract.
    raise NotImplementedError("TODO: implement the FTC RSS parser")


PARSERS = {"eurlex": parse_eurlex, "edpb": parse_edpb,
           "uk_legislation": parse_uk_legislation,
           "federal_register": parse_federal_register, "ftc": parse_ftc}
