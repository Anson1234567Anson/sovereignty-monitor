-- No extensions or Supabase-specific roles are needed.
CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    url TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS items (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES sources(id),
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    published TIMESTAMPTZ,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    summary TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE CHECK (content_hash ~ '^[0-9a-f]{64}$'),
    digested_at TIMESTAMPTZ
);

-- Topics are keyword labels; each item can have several, each label many items.
CREATE TABLE IF NOT EXISTS item_topics (
    item_id BIGINT NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    topic TEXT NOT NULL CHECK (topic <> ''),
    PRIMARY KEY (item_id, topic)
);

CREATE TABLE IF NOT EXISTS host_requests (
    origin TEXT PRIMARY KEY,
    requested_at TIMESTAMPTZ NOT NULL
);
