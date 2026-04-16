-- name: CreateCampaign :one
INSERT INTO campaigns (
    advertiser_id,
    name,
    status,
    total_budget,
    start_date,
    end_date
) VALUES ($1, $2, $3, $4, $5, $6)
RETURNING *;

-- name: GetCampaign :one
SELECT * FROM campaigns
WHERE id = $1 LIMIT 1;

-- name: ListCampaigns :many
SELECT * FROM campaigns
ORDER BY created_at DESC;

-- name: ListCampaignsByAdvertiser :many
SELECT * FROM campaigns
WHERE advertiser_id = $1
ORDER BY created_at DESC;

-- name: UpdateCampaign :one
UPDATE campaigns
SET
    name = $2,
    status = $3,
    total_budget = $4,
    start_date = $5,
    end_date = $6
WHERE id = $1
RETURNING *;

-- name: UpdateCampaignStatus :one
UPDATE campaigns
SET status = $2
WHERE id = $1
RETURNING *;

-- name: DeleteCampaign :exec
DELETE FROM campaigns
WHERE id = $1;

-- name: GetActiveCampaigns :many
SELECT * FROM campaigns
WHERE status = 'ACTIVE'
AND start_date <= NOW()
AND (end_date IS NULL OR end_date >= NOW())
ORDER BY created_at DESC;

