# Step 3: real Postgres verification

Run on 20 October 2026, using Python 3.13, psycopg 3.3.6 and Postgres 17.11.
Installed `postgresql-binaries==17.11.0` into the local virtual environment
without sudo. Initialized a temporary cluster under `/tmp`, listening on
`127.0.0.1:55432`, with local trust authentication. `DATABASE_URL` was exported
in the command environment; no credentials or connection strings were written
to application files. The server was run in a persistent foreground session
because this execution environment stops background children after a command.

Commands below were run from `monitor`. Outputs are copied from the real runs.
No HTTP responses were mocked for the two fetch commands. Database tests used
isolated schemas on this same real server.

## Server

```text
$ postgres --version
postgres (PostgreSQL) 17.11
```

## Apply migrations twice

```text
$ .venv/bin/python migrate.py
APPLIED 001_tables.sql
APPLIED 002_indexes.sql
MIGRATE applied=2 up_to_date=true
$ .venv/bin/python migrate.py
MIGRATE applied=0 up_to_date=true
```

Recorded migration rows, queried with psql:

```text
 version |      name
---------+-----------------
       1 | 001_tables.sql
       2 | 002_indexes.sql
(2 rows)
```

## Tests

```text
$ .venv/bin/python -m pytest -q
...........x.........................                                    [100%]
36 passed, 1 xfailed in 0.33s
```

The expected failure is the unchanged FTC exercise. Tests also replay both SQL
files directly, verify failed migrations roll back DDL and their version records,
and check publication-window boundaries against actual Postgres timestamps.

## First live fetch

```text
$ .venv/bin/python fetch.py
eurlex: items=100 new=100 duplicates=0 tagged_new=0
edpb: items=10 new=10 duplicates=0 tagged_new=10
uk_legislation: items=20 new=20 duplicates=0 tagged_new=0
federal_register: items=20 new=20 duplicates=0 tagged_new=1
ftc: SKIP learning exercise: TODO: implement the FTC RSS parser
TOTAL sources=5 fetched=5 parsed=4 items=150 inserted=150 duplicates=0 tagged_new=11 todo=1 errors=0
```

## Second live fetch, same database

```text
$ .venv/bin/python fetch.py
eurlex: items=100 new=0 duplicates=100 tagged_new=0
edpb: items=10 new=0 duplicates=10 tagged_new=0
uk_legislation: items=20 new=0 duplicates=20 tagged_new=0
federal_register: items=20 new=0 duplicates=20 tagged_new=0
ftc: SKIP learning exercise: TODO: implement the FTC RSS parser
TOTAL sources=5 fetched=5 parsed=4 items=150 inserted=0 duplicates=150 tagged_new=0 todo=1 errors=0
```

Row counts after both runs, queried with psql:

```text
 sources | items | item_topics
---------+-------+-------------
       5 |   150 |          25
(1 row)
```

## Digest delivery and rerun

```text
$ .venv/bin/python digest.py --output /tmp/monitor-step3-digest.md
DIGEST new_tagged_items=11 topics=4 output=/tmp/monitor-step3-digest.md
$ .venv/bin/python digest.py --output /tmp/monitor-step3-digest-rerun.md
DIGEST new_tagged_items=0 topics=0 output=/tmp/monitor-step3-digest-rerun.md
```

## Demo query

Ran the unmodified query file through the installed Postgres `psql` binary,
with `PGTZ=UTC` so output uses UTC, and `ON_ERROR_STOP=1`:

```text
$ "$PG_BIN/psql" "$DATABASE_URL" -X -v ON_ERROR_STOP=1 -P pager=off -f queries/gdpr_last_7_days.sql
 id  | source |                                      title                                       |                                                         url                                                         |       published        |          fetched_at
-----+--------+----------------------------------------------------------------------------------+---------------------------------------------------------------------------------------------------------------------+------------------------+-------------------------------
 101 | edpb   | Norwegian DPA fines Xandr EUR 8 600 000 for unlawful processing of personal data | https://www.edpb.europa.eu/news/norwegian-dpa-fines-xandr-eur-8-600-000-for-unlawful-processing-of-personal-data_en | 2026-10-16 12:00:00+00 | 2026-10-20 03:50:22.505003+00
 102 | edpb   | EDPB publishes statement on the data protection challenges of smart glasses      | https://www.edpb.europa.eu/news/edpb-publishes-statement-on-the-data-protection-challenges-of-smart-glasses_en      | 2026-10-13 12:00:00+00 | 2026-10-20 03:50:22.508489+00
(2 rows)
```

## FTC preservation and dependency check

Both SHA-256 values were identical before and after this change, preserving the
entire parser file and parser tests, including the FTC stub and strict marker:

```text
e4d7d3035d53ae670a1101b88507d14430e2f4e3b4b9fd2a7a1c2874972c981e  parsers.py
e3e98722c27a5d1f105c852f26bc64286a4b3ba3bd26240a9fcca61231e8c104  tests/test_parsers.py
```

```text
$ .venv/bin/python -m pip check
No broken requirements found.
```

After verification, the temporary server was shut down cleanly:

```text
Temporary Postgres server stopped cleanly.
```
