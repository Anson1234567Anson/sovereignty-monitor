-- A rolling seven-day publication window. Unknown and future dates are excluded.
SELECT i.id, s.id AS source, i.title, i.url, i.published, i.fetched_at
FROM items AS i
JOIN sources AS s ON s.id = i.source_id
JOIN item_topics AS t ON t.item_id = i.id
WHERE t.topic = 'GDPR'
  AND i.published >= CURRENT_TIMESTAMP - INTERVAL '7 days'
  AND i.published <= CURRENT_TIMESTAMP
ORDER BY i.published DESC, i.id;
