-- name: CreateAd :one
INSERT INTO ads (ad_set_id,
                 headline,
                 description,
                 creative_type,
                 media_url,
                 destination_url,
                 status)
VALUES ($1, $2, $3, $4, $5, $6, $7)
RETURNING *;

-- name: GetAd :one
SELECT *
FROM ads
WHERE id = $1
LIMIT 1;

-- name: ListAdsByAdSet :many
SELECT *
FROM ads
WHERE ad_set_id = $1
ORDER BY created_at DESC;

-- name: ListActiveAds :many
SELECT *
FROM ads
WHERE status = 'ACTIVE'
ORDER BY updated_at DESC;

-- name: UpdateAdStatus :one
UPDATE ads
SET status = $2
WHERE id = $1
RETURNING *;

-- name: GetAdWithTargeting :one
SELECT a.id,
       a.ad_set_id,
       a.headline,
       a.description,
       a.creative_type,
       a.media_url,
       a.destination_url,
       a.status,
       a.created_at,
       a.updated_at
FROM ads a
WHERE a.id = $1
  AND a.status = 'ACTIVE'
LIMIT 1;

-- name: ListAllActiveAdsForIndex :many
SELECT a.id,
       a.ad_set_id,
       a.headline,
       a.description,
       a.creative_type,
       a.media_url,
       a.destination_url,
       a.status,
       ads.bid_amount_cents,
       ads.daily_budget_cents,
       ads.pricing_model,
       c.id     as campaign_id,
       c.advertiser_id,
       c.status as campaign_status,
       c.start_date,
       c.end_date,
       a.created_at,
       a.updated_at
FROM ads a
         JOIN ad_sets ads ON a.ad_set_id = ads.id
         JOIN campaigns c ON ads.campaign_id = c.id
WHERE a.status = 'ACTIVE'
  AND c.status = 'ACTIVE'
  AND c.start_date <= NOW()
  AND (c.end_date IS NULL OR c.end_date > NOW());


-- name: ListChangedAdsForIndex :many
SELECT a.id,
       a.ad_set_id,
       a.headline,
       a.description,
       a.creative_type,
       a.media_url,
       a.destination_url,
       a.status,
       ads.bid_amount_cents,
       ads.daily_budget_cents,
       ads.pricing_model,
       c.id     as campaign_id,
       c.advertiser_id,
       c.status as campaign_status,
       c.start_date,
       c.end_date,
       a.created_at,
       a.updated_at
FROM ads a
         JOIN ad_sets ads ON a.ad_set_id = ads.id
         JOIN campaigns c ON ads.campaign_id = c.id
WHERE a.id IN (SELECT DISTINCT a.id
               FROM ads a
                        JOIN ad_sets ads ON a.ad_set_id = ads.id
                        JOIN campaigns c ON ads.campaign_id = c.id
               WHERE a.updated_at > $1
                  OR ads.updated_at > $1
                  OR c.updated_at > $1);


