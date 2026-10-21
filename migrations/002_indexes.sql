-- Unique constraints already index item URL, content hash and source URL.
CREATE INDEX IF NOT EXISTS items_source_published_idx
    ON items (source_id, published DESC);
CREATE INDEX IF NOT EXISTS items_published_idx ON items (published DESC);
CREATE INDEX IF NOT EXISTS items_fetched_at_idx ON items (fetched_at DESC);
CREATE INDEX IF NOT EXISTS items_pending_digest_idx
    ON items (id) WHERE digested_at IS NULL;
-- The primary key covers item -> topics; this index covers topic -> items.
CREATE INDEX IF NOT EXISTS item_topics_topic_item_idx ON item_topics (topic, item_id);
