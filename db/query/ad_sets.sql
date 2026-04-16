-- name: CreateAdSet :one
INSERT INTO ad_sets (
    campaign_id,
    name,
    bid_amount_cents,
    daily_budget_cents,
    pricing_model
) VALUES ($1, $2, $3, $4, $5)
RETURNING *;

-- name: GetAdSet :one
SELECT * FROM ad_sets
WHERE id = $1 LIMIT 1;

-- name: ListAdSetsByCampaign :many
SELECT * FROM ad_sets
WHERE campaign_id = $1
ORDER BY created_at DESC;

