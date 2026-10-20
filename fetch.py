"""Fetch only the five configured sources plus their same-origin robots.txt."""
import argparse
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
import yaml

from parsers import PARSERS
from storage import connect, save, throttle
from tagger import tag

ROOT = Path(__file__).resolve().parent
VERIFIED = {
    "eurlex": ("https://eur-lex.europa.eu/EN/display-feed.rss?rssId=222", 10),
    "edpb": ("https://www.edpb.europa.eu/feed/news_en", 0),
    "uk_legislation": ("https://www.legislation.gov.uk/new/data.feed", 5),
    "federal_register": ("https://www.federalregister.gov/api/v1/documents.json?per_page=1", 0),
    "ftc": ("https://www.ftc.gov/feeds/press-release-consumer-protection.xml", 5),
}


def origin(url):
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}"


def get(client, db, url, delay, robots=None):
    site = origin(url)
    for _ in range(6):
        if origin(url) != site:
            raise ValueError("Refusing a redirect to another origin")
        if robots and not robots.can_fetch(client.headers["User-Agent"], url):
            raise ValueError(f"robots.txt disallows {url}")
        throttle(db, site, delay)
        response = client.get(url)
        if response.is_redirect:
            url = urljoin(url, response.headers["location"])
            continue
        return response
    raise ValueError("Too many redirects")


def robots_policy(client, db, url, minimum_delay):
    robots_url = origin(url) + "/robots.txt"
    response = get(client, db, robots_url, minimum_delay)
    policy = RobotFileParser(robots_url)
    if response.status_code == 404:
        policy.parse(["User-agent: *", "Allow: /"])
    else:
        response.raise_for_status()
        if "<html" in response.text.lower() or "<!doctype html" in response.text.lower():
            raise ValueError("robots.txt returned an HTML challenge; skipping source")
        policy.parse(response.text.splitlines())
    agent = client.headers["User-Agent"]
    delays = [minimum_delay, policy.crawl_delay(agent) or 0,
              policy.crawl_delay("*") or 0]
    rate = policy.request_rate(agent)
    if rate:
        delays.append(rate.seconds / rate.requests)
    return policy, max(delays)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "sources.yaml")
    parser.add_argument("--db", type=Path, default=ROOT / "monitor.sqlite3")
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text())
    sources = config["sources"]
    if len(sources) != 5 or {s["id"] for s in sources} != set(VERIFIED):
        raise ValueError("Configuration must contain exactly the five verified sources")
    for source in sources:
        expected_url, _ = VERIFIED[source["id"]]
        if source["url"] != expected_url or source["parser"] != source["id"]:
            raise ValueError(f"Unverified source configuration: {source['id']}")
    counts = dict(sources=5, fetched=0, parsed=0, items=0, inserted=0,
                  duplicates=0, tagged_new=0, todo=0, errors=0)
    db = connect(args.db)
    timeout = httpx.Timeout(float(config["timeout_seconds"]), connect=10)
    try:
        with httpx.Client(headers={"User-Agent": config["user_agent"]},
                          timeout=timeout, follow_redirects=False) as client:
            for source in sources:
                name, url = source["id"], source["url"]
                try:
                    delay = max(float(source["crawl_delay"]), VERIFIED[name][1])
                    robots, delay = robots_policy(client, db, url, delay)
                    response = get(client, db, url, delay, robots)
                    response.raise_for_status()
                    counts["fetched"] += 1
                    items = PARSERS[source["parser"]](response.content, name, url)
                    counts["parsed"] += 1
                    new = tagged = 0
                    for item in items:
                        topics = tag(item.title, item.summary)
                        if save(db, item, topics):
                            new += 1
                            tagged += bool(topics)
                    counts["items"] += len(items)
                    counts["inserted"] += new
                    counts["duplicates"] += len(items) - new
                    counts["tagged_new"] += tagged
                    print(f"{name}: items={len(items)} new={new} "
                          f"duplicates={len(items) - new} tagged_new={tagged}", flush=True)
                except NotImplementedError as exc:
                    counts["todo"] += 1
                    print(f"{name}: SKIP learning exercise: {exc}", flush=True)
                except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                    counts["errors"] += 1
                    print(f"{name}: ERROR {exc}", flush=True)
    finally:
        db.close()
    print("TOTAL " + " ".join(f"{key}={value}" for key, value in counts.items()))
    return 1 if counts["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
