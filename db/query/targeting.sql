-- name: CreateAdTargetingKeyword :one
INSERT INTO ad_targeting_keyword (ad_id, keyword, relevance_score)
VALUES ($1, $2, $3)
RETURNING *;

-- name: CreateAdTargetingTopic :one
INSERT INTO ad_targeting_topic (ad_id, topic_id, relevance_score)
VALUES ($1, $2, $3)
RETURNING *;

-- name: CreateAdTargetingEntity :one
INSERT INTO ad_targeting_entity (ad_id, entity_id, entity_type)
VALUES ($1, $2, $3)
RETURNING *;

-- name: CreateAdTargetingCountry :one
INSERT INTO ad_targeting_country (ad_id, country_iso_code)
VALUES ($1, $2)
RETURNING *;

-- name: CreateAdTargetingDevice :one
INSERT INTO ad_targeting_device (ad_id, device_type)
VALUES ($1, $2)
RETURNING *;

-- name: GetAdTargetingKeywords :many
SELECT * FROM ad_targeting_keyword
WHERE ad_id = $1;

-- name: GetAdTargetingTopics :many
SELECT * FROM ad_targeting_topic
WHERE ad_id = $1;

-- name: GetAdTargetingEntities :many
SELECT * FROM ad_targeting_entity
WHERE ad_id = $1;

-- name: GetAdTargetingCountries :many
SELECT * FROM ad_targeting_country
WHERE ad_id = $1;

-- name: GetAdTargetingDevices :many
SELECT * FROM ad_targeting_device
WHERE ad_id = $1;

-- name: GetAdTargetingKeywordsByAdIds :many
SELECT * FROM ad_targeting_keyword
WHERE ad_id = ANY($1::int[])
ORDER BY ad_id, relevance_score DESC;

-- name: GetAdTargetingTopicsByAdIds :many
SELECT att.id, att.ad_id, att.topic_id, att.relevance_score, att.updated_at, it.tier
FROM ad_targeting_topic att
JOIN iab_topics it ON att.topic_id = it.id
WHERE att.ad_id = ANY($1::int[])
ORDER BY att.ad_id, att.relevance_score DESC;

-- name: GetAdTargetingEntitiesByAdIds :many
SELECT * FROM ad_targeting_entity
WHERE ad_id = ANY($1::int[])
ORDER BY ad_id;

-- name: GetAdTargetingCountriesByAdIds :many
SELECT * FROM ad_targeting_country
WHERE ad_id = ANY($1::int[])
ORDER BY ad_id;

-- name: GetAdTargetingDevicesByAdIds :many
SELECT * FROM ad_targeting_device
WHERE ad_id = ANY($1::int[])
ORDER BY ad_id;

