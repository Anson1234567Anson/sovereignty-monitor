# Sovereignty monitor prototype

A small, local Python monitor based on the five verified feeds/API in
[`../sources.md`](../sources.md). It uses keyword rules, not an LLM. It fetches
no article pages and adds no other publishers. Robots metadata comes only from
the same five sites. FTC collection reaches an intentional parser TODO.

## Run

From the repository root (Python 3.10 or newer):

```bash
python3 -m venv monitor/.venv
monitor/.venv/bin/python -m pip install -r monitor/requirements.txt
cd monitor
.venv/bin/python -m pytest -q
.venv/bin/python fetch.py
.venv/bin/python digest.py
```

Open `monitor/digest.md` from the repository root, or `digest.md` if you are
already inside `monitor`. Commands work from any directory using their paths;
default database, configuration and digest paths are relative to the scripts.
The fetcher prints per-source counts and a total. Tests are entirely offline.

## Files in plain English

| File | What it does |
| --- | --- |
| `sources.yaml` | Lists exactly the five verified URLs, their parsers and minimum delays, plus the identifying User-Agent and timeout. |
| `requirements.txt` | Lists the libraries installed into the local virtual environment. |
| `models.py` | Defines one consistent record: source, title, URL, publication time and summary. |
| `parsers.py` | Reads EUR-Lex RSS, EDPB RSS, UK Atom and Federal Register JSON. Removes markup from text. Contains the FTC exercise. |
| `tagger.py` | Matches keywords in titles and summaries against seven topics. Edit `KEYWORDS` to tune it. |
| `storage.py` | Creates SQLite tables, hashes text, prevents duplicate records and remembers request times. |
| `fetch.py` | Checks robots rules, waits between requests, downloads each endpoint and saves records and tags. |
| `digest.py` | Writes new tagged records grouped by topic, with source links, dates and summaries; then marks them as included. |
| `pytest.ini` | Tells pytest where to find the modules and tests. |
| `tests/test_storage.py` | Checks deduplication by URL and by normalized content hash. |
| `tests/test_tagger.py` | Checks all topics, multiple tags, spelling variants and word boundaries. |
| `tests/test_parsers.py` | Checks the four adapters and describes the intentionally unfinished FTC adapter. |
| `tests/test_digest.py` | Checks topic grouping, filtering and delivery state. |
| `.gitignore` | Keeps the virtual environment, database, digest and caches out of version control. |
| `.venv/` | Holds this prototype's Python interpreter and installed libraries. |
| `monitor.sqlite3` | Generated local database holding items, tags and per-site request times. |
| `digest.md` | Generated Markdown containing the latest batch of new tagged items. |

## FTC learning exercise

Implement `parse_ftc` in `parsers.py`. Its signature and output match the other
RSS adapters; the shared helper is available. The expected behaviour is in
`test_ftc_expected_rss_contract`. It currently raises `NotImplementedError`, so
pytest reports one **xfail** (an intentionally failing/skipped test). Once you
implement the adapter, remove the `xfail` marker. Its strict setting reports an
unexpected pass as a failure to remind you to enable the test normally. The
fetcher logs this TODO and continues; it stores no FTC items until implemented.

## Collection and storage details

The identifying User-Agent is `SovereigntyMonitor/0.1`; customize its descriptive
text in YAML with your contact information before scheduling it. Each source
gets one robots request and one feed/API request, unless a request is blocked or
fails. Same-origin redirects also count as requests. Cross-origin redirects are
refused. The minimum crawl delays recorded in `sources.md` are 10 seconds for
EUR-Lex, 5 for UK legislation, and 5 for FTC. The fetcher applies the greater of
those minima, configured delays, and current robots crawl delays. It also honors
robots request-rate intervals. Request starts persist in SQLite across runs.
Run one fetch/digest process at a time; this is a sequential prototype.

HTTP calls have a configured 30-second inactivity timeout and a 10-second
connection timeout. Missing robots files (404) permit collection; other failed
robots requests and HTML challenges skip that source. Blocked paths, HTTP errors
(including 429), timeouts and malformed responses are printed as errors with no
automatic retry or access bypass. Other sources still run. The fetch command
exits nonzero on those errors; the deliberate FTC TODO is counted separately.

SQLite `items` stores `source`, `title`, `url`, `published`, `summary`, `hash`,
plus an ID and digest timestamp. Tags live in `item_topics`. Both URL and SHA-256
hash have unique constraints. The hash uses normalized title and summary only,
so identical text with a different URL or date still deduplicates. An existing
URL is never updated; this prototype tracks new records, not revisions.
Publication dates stay ISO-formatted when available; missing feed dates are null.
All parsed items are saved, even when none of the seven topics match.

The digest includes only new tagged items since the last successful digest.
An item matching several topics appears in each group but counts once. The next
run replaces `digest.md`; copy it elsewhere if you want an archive. Untagged
items remain stored but are not delivered. Keyword matching is deliberately
simple and can miss relevant wording or produce false positives. Guidance,
proposals and enforcement announcements should not be read as enacted law.

Feed windows are finite. There is no pagination, backfill, scheduler or article
scraping. The exact verified Federal Register URL requests `per_page=1`, but the
observed response contained 20 records; all returned records are parsed. This
single-page collection is a demonstration, not complete coverage. To repeat a clean
experiment, use a different database: `fetch.py --db trial.sqlite3`, followed by
`digest.py --db trial.sqlite3 --output trial.md`. `fetch.py --config` accepts a
YAML path, but validation keeps endpoint URLs locked to the verified five.

## Actual first run (20 October 2026)

`pytest -q`: **19 passed, 1 xfailed** (FTC exercise).

| Source | Parsed items | New tagged items |
| --- | ---: | ---: |
| EUR-Lex | 100 | 0 |
| EDPB | 10 | 10 |
| UK legislation | 20 | 0 |
| Federal Register | 20 | 1 |
| FTC | TODO, feed fetched | 0 |

Fetch totals: **5 fetched, 4 parsed, 150 inserted, 0 duplicates, 11 new tagged,
1 TODO, 0 errors**. Digest: **11 distinct items across 4 topics** (GDPR,
cross-border transfer, cybersecurity and privacy). An item can appear in several
topic groups. Later runs will have different counts as the feeds and database change.
