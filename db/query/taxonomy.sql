-- name: CreateIABTopic :exec
INSERT INTO iab_topics (
    id,
    name,
    parent_id,
    tier,
    type
) VALUES ($1, $2, $3, $4, $5)
ON CONFLICT (id) DO NOTHING;

-- name: GetIABTopic :one
SELECT * FROM iab_topics
WHERE id = $1 LIMIT 1;

-- name: ListIABTopics :many
SELECT * FROM iab_topics
ORDER BY id;

-- name: ListIABTopicsByType :many
SELECT * FROM iab_topics
WHERE type = $1
ORDER BY id;

-- name: CreateIABTopicMapping :exec
INSERT INTO iab_topic_mapping (
    content_topic_id,
    product_topic_id
) VALUES ($1, $2)
ON CONFLICT (content_topic_id, product_topic_id) DO NOTHING;

-- name: GetProductTopicsByContentTopic :many
SELECT p.* FROM iab_topics p
INNER JOIN iab_topic_mapping m ON p.id = m.product_topic_id
WHERE m.content_topic_id = $1;

-- name: GetContentTopicsByProductTopic :many
SELECT c.* FROM iab_topics c
INNER JOIN iab_topic_mapping m ON c.id = m.content_topic_id
WHERE m.product_topic_id = $1;

-- name: CountIABTopics :one
SELECT COUNT(*) FROM iab_topics;

-- name: CountIABTopicMappings :one
SELECT COUNT(*) FROM iab_topic_mapping;
