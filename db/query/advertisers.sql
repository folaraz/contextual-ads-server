-- name: CreateAdvertiser :one
INSERT INTO advertisers (name, website)
VALUES ($1, $2)
RETURNING *;

-- name: GetAdvertiser :one
SELECT * FROM advertisers
WHERE id = $1 LIMIT 1;

-- name: ListAdvertisers :many
SELECT * FROM advertisers
ORDER BY created_at DESC;

-- name: UpdateAdvertiser :one
UPDATE advertisers
SET name = $2, website = $3
WHERE id = $1
RETURNING *;

-- name: DeleteAdvertiser :exec
DELETE FROM advertisers
WHERE id = $1;

