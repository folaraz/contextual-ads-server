-- name: CreatePublisher :one
INSERT INTO publishers (name, domain)
VALUES ($1, $2)
RETURNING *;

-- name: GetPublisher :one
SELECT * FROM publishers
WHERE id = $1;

-- name: ListPublishers :many
SELECT * FROM publishers
ORDER BY created_at DESC;

-- name: UpdatePublisher :one
UPDATE publishers
SET name = $2,
    domain = $3,
    updated_at = NOW()
WHERE id = $1
RETURNING *;

-- name: DeletePublisher :exec
DELETE FROM publishers
WHERE id = $1;

