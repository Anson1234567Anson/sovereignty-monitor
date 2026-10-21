# Sovereignty monitor prototype

A small Python monitor based on the five verified feeds/API in
[`../sources.md`](../sources.md). It uses keyword rules, fetches no article pages
and adds no other publishers. FTC collection reaches an intentional parser TODO.
Storage uses psycopg 3 and Postgres 17, including a Supabase Postgres database.

## Run

From the repository root (Python 3.10 or newer):

```bash
python3 -m venv monitor/.venv
monitor/.venv/bin/python -m pip install -r monitor/requirements.txt
cd monitor

# Paste the database connection string at the hidden prompt, not into a file.
read -r -s -p 'DATABASE_URL: ' DATABASE_URL
printf '\n'
export DATABASE_URL

.venv/bin/python migrate.py
.venv/bin/python migrate.py  # No new migrations on the second run.
.venv/bin/python fetch.py
.venv/bin/python digest.py
psql "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -f queries/gdpr_last_7_days.sql
```

`DATABASE_URL` is required by migrations, collection, digests and database tests.
There is no default connection string, `.env` loader or `--db` option. Keep real
credentials in the process environment or your deployment's secret settings.
For Supabase, copy a direct or session-mode connection string from the project's
Connect panel, with SSL configured in that string. These commands use database
sessions; choose direct or session mode rather than transaction pooling. See
[Supabase's connection guide](https://supabase.com/docs/guides/database/connecting-to-postgres).
Use a database role allowed to create the tables and indexes for migration.

Open `monitor/digest.md` from the repository root. Script defaults for the
configuration, migrations and digest are relative to the script files, so the
commands also work from another directory when given their full paths. The old
`monitor.sqlite3` file is no longer used; existing SQLite data is not imported.
A fresh Postgres database fills from the current feed windows.

## Tables and why they are separate

| Table | What it stores and why |
| --- | --- |
| `sources` | One row per source ID, such as `edpb`, and its unique feed URL. Articles refer to this row rather than repeating feed metadata. The URL can be null until the fetcher registers the configured endpoint. |
| `items` | One article's title, URL, summary, source ID, content hash and timestamps. Both URL and content hash have separate unique constraints, so either kind of duplicate is rejected. |
| `item_topics` | One `(item_id, topic)` pair per match. An article can match several topics, and each topic can contain many articles. The combined primary key prevents repeated tags; deleting an item deletes its tag links. Labels come from `tagger.py`, so a separate topic catalogue is unnecessary here. |
| `host_requests` | The last request start per origin, preserving crawl delays across command invocations. |
| `schema_migrations` | Each applied migration's number, filename, checksum and application time. This makes repeat migration runs safe and catches edits to already applied SQL. |

`items.published` is a nullable `timestamptz`: it represents the publication
instant, or null when the feed has no date. Date-only and timezone-free parser
values are interpreted as UTC. `fetched_at` is a non-null `timestamptz` set by
Postgres when an item is first inserted. It answers when this monitor first saw
the article, separately from when it was published. `digested_at` is a nullable
`timestamptz` recording successful digest delivery. Connections opened by
`storage.py` display dates in UTC. Duplicate fetches leave all three timestamps unchanged.

The SHA-256 content hash uses normalized title and summary only. Identical text
under another URL, source or publication date still deduplicates. Inserts use
`ON CONFLICT DO NOTHING`, with `RETURNING id` to tell whether an item was new.
Saving an item and all its topic links is one transaction. Existing URLs are not
updated; this prototype tracks new articles rather than revisions. All parsed
items are stored, including those with no matching topic.

Unique constraints already provide indexes for URLs and content hashes. Extra
indexes support publication windows, source-and-date lookups, fetch times,
undelivered items, and topic-to-item lookup. The topic-link primary key supports
the reverse lookup from an item to its topics.

## Migrations and the demo query

`migrations/001_tables.sql` creates the tables; `002_indexes.sql` adds indexes.
Both use `IF NOT EXISTS` and can be replayed directly. `migrate.py` applies
unrecorded files in numeric order and records their versions. A transaction
covers the SQL and version records, so a failure leaves neither partial DDL nor
a falsely recorded success. A transaction-scoped advisory lock serializes
concurrent migration runners. Add a new numbered file for schema changes;
do not edit an already applied file. These migrations require no extensions or
Supabase-specific roles.

`queries/gdpr_last_7_days.sql` joins sources, articles and tags to return articles
tagged `GDPR` published in the last seven days, newest first. This is a rolling
publication window, not a fetch-time window; unknown dates and future publication
dates are excluded. A zero-row result is valid when current feeds contain no
recent GDPR matches.

## Tests against a real local Postgres

Database tests require `DATABASE_URL` pointing to a real test server. They create
a unique schema per test, apply the migrations, and drop only that schema after
the test. They never truncate collected articles in `public`. The test role needs
permission to create schemas. Tests cover deduplication, topic relationships,
timezones, rollback, migration reruns, digest delivery and the demo query.
HTTP/parser fixtures do not call live sites; run `fetch.py` separately for a live
collection check. The database tests fail if Postgres is unavailable.

If a Postgres 17 server is already available, set `DATABASE_URL` to it and run:

```bash
cd monitor  # If currently at the repository root.
.venv/bin/python -m pytest -q
```

For Linux, this optional local setup installs binaries without sudo (the binary
package helper needs Python 3.12 or newer). Run from `monitor`:

```bash
.venv/bin/python -m pip install postgresql-binaries==17.11.0
PG_BIN="$(.venv/bin/python -c 'import postgresql_binaries; print(postgresql_binaries.bin())')"
PG_DATA="$(mktemp -d /tmp/monitor-pg17-XXXXXX)"
"$PG_BIN/initdb" -D "$PG_DATA/data" -U monitor --auth=trust --encoding=UTF8 --locale=C
"$PG_BIN/pg_ctl" -D "$PG_DATA/data" -l "$PG_DATA/server.log" \
  -o "-h 127.0.0.1 -p 55432 -k $PG_DATA" -w start
"$PG_BIN/createdb" -h 127.0.0.1 -p 55432 -U monitor monitor
```

This temporary server listens only on localhost and uses password-free local
trust authentication. Set `DATABASE_URL` using the hidden prompt above, with
host `127.0.0.1`, port `55432`, user `monitor` and database `monitor`. Then run:

```bash
.venv/bin/python migrate.py
.venv/bin/python migrate.py
.venv/bin/python -m pytest -q
.venv/bin/python fetch.py
.venv/bin/python fetch.py  # Unchanged feed records should all be duplicates.
.venv/bin/python digest.py --output /tmp/monitor-digest.md
"$PG_BIN/psql" "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -f queries/gdpr_last_7_days.sql
"$PG_BIN/pg_ctl" -D "$PG_DATA/data" -m fast -w stop
```

The [binary package documentation](https://pypi.org/project/postgresql-binaries/17.11.0/)
explains its installation. Recorded real outputs for this change are in
[`verification.md`](verification.md).

## Files in plain English

| File | What it does |
| --- | --- |
| `sources.yaml` | Lists the five verified URLs, parsers and minimum delays, identifying User-Agent and timeout. |
| `requirements.txt` | Lists Python dependencies, including psycopg 3 with its binary driver. |
| `models.py` | Defines the common parser record: source, title, URL, publication time and summary. |
| `parsers.py` | Reads EUR-Lex RSS, EDPB RSS, UK Atom and Federal Register JSON. Contains the unchanged FTC exercise. |
| `tagger.py` | Matches title/summary keywords against seven topics. Edit `KEYWORDS` to tune it. |
| `storage.py` | Opens Postgres from `DATABASE_URL`, hashes text, saves articles/tags and remembers request times. |
| `migrate.py`, `migrations/` | Apply and record numbered schema changes. |
| `fetch.py` | Checks robots rules, waits between requests, downloads endpoints and saves records and tags. |
| `digest.py` | Writes new tagged records grouped by topic, then marks them as included. |
| `queries/` | Holds the example GDPR publication-window query. |
| `tests/`, `pytest.ini` | Parser/tagger tests and real Postgres integration tests. |
| `.gitignore` | Excludes the virtual environment, old SQLite databases, generated digest, caches and environment files. |

## FTC learning exercise

Implement `parse_ftc` in `parsers.py`. Its signature and output match the other
RSS adapters; the shared helper is available. The expected behaviour is in
`test_ftc_expected_rss_contract`. It raises `NotImplementedError`, so pytest
reports one **xfail**. Once you implement the adapter, remove the `xfail` marker.
Its strict setting reports an unexpected pass as a failure to remind you to
enable the test normally. The fetcher logs this TODO and continues; it stores
no FTC items until implemented. The stub and its strict-xfail test are unchanged
by the Postgres migration.

## Collection and delivery details

The identifying User-Agent is `SovereigntyMonitor/0.1`; customize its descriptive
text in YAML with your contact information before scheduling it. Each source
gets one robots request and one feed/API request, unless blocked or failed.
Same-origin redirects also count as requests; cross-origin redirects are refused.
The minimum crawl delays are 10 seconds for EUR-Lex, 5 for UK legislation, and 5
for FTC. The fetcher applies the greatest of those minima, configured delays,
and current robots crawl delays. It honors robots request-rate intervals and
persists request starts in Postgres across runs. Run one fetch/digest process at
a time; this is a sequential prototype.

HTTP calls use a 30-second inactivity timeout and a 10-second connection timeout.
Missing robots files (404) permit collection; other failed robots requests and
HTML challenges skip that source. Blocked paths, HTTP errors, timeouts and
malformed responses are printed with no automatic retry or access bypass. Other
sources still run. Fetch exits nonzero on those errors; the FTC TODO is counted
separately.

The digest includes only new tagged items since the last successful digest.
An item matching several topics appears in each group but counts once. Output
is replaced atomically before delivery timestamps are saved; a failed output
write leaves items pending. The next run replaces the file, so copy it elsewhere
for an archive. Untagged items remain stored but are not delivered. Keyword rules
can miss relevant wording or produce false positives. Guidance, proposals and
enforcement announcements should not be read as enacted law.

Feed windows are finite. There is no pagination, backfill, scheduler or article
scraping. The verified Federal Register URL requests `per_page=1`, but the
observed response contained 20 records; all returned records are parsed. This
single-page collection is a demonstration, not complete coverage. Use a separate
Postgres database via `DATABASE_URL` for a clean collection experiment.
`fetch.py --config` accepts a YAML path, while validation locks endpoints to the
verified five.
