package campaigns

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
	"time"

	db "github.com/folaraz/contextual-ads-server/db/sqlc"
	"github.com/folaraz/contextual-ads-server/internal/models"
	"github.com/folaraz/contextual-ads-server/internal/observability"
	"github.com/folaraz/contextual-ads-server/internal/publisher"
	"github.com/folaraz/contextual-ads-server/internal/validation"
	goredis "github.com/redis/go-redis/v9"
)

type CampaignService struct {
	db          *sql.DB
	queries     *db.Queries
	publisher   *publisher.KafkaPublisher
	redisClient *goredis.Client
}

func NewCampaignService(database *sql.DB, pub *publisher.KafkaPublisher, redisClient *goredis.Client) *CampaignService {
	return &CampaignService{
		db:          database,
		queries:     db.New(database),
		publisher:   pub,
		redisClient: redisClient,
	}
}

// CreateCampaignRequest todo this is too complex, I need to break down the creation process. Maybe have a sepearate endpoint and service for ads and cmaping. we can have a pending flag until ads has been completely setup
type CreateCampaignRequest struct {
	AdvertiserID       int32         `validate:"required"`
	Campaign           CampaignInput `validate:"required"`
	AdSet              AdSetInput    `validate:"required"`
	Ad                 AdInput       `validate:"required"`
	TargetingKeywords  []string
	TargetingTopics    []TopicTargeting  `validate:"omitempty,dive"`
	TargetingEntities  []EntityTargeting `validate:"omitempty,dive"`
	TargetingCountries []string          `validate:"omitempty,dive,len=2"`
	TargetingDevices   []string          `validate:"omitempty,dive,oneof=mobile desktop tablet"`
}

type CampaignInput struct {
	Name             string     `validate:"required,min=1"`
	Status           string     `validate:"omitempty,status"`
	TotalBudgetCents int64      `validate:"gte=0"`
	StartDate        time.Time  `validate:"required"`
	EndDate          *time.Time `validate:"omitempty,gtfield=StartDate"`
}

type AdSetInput struct {
	Name             string `validate:"required,min=1"`
	BidAmountCents   int64  `validate:"gte=0"`
	DailyBudgetCents int64  `validate:"gte=0"`
	PricingModel     string `validate:"required,pricing_model"`
}

type AdInput struct {
	Headline       string `validate:"required,min=1"`
	Description    string
	CreativeType   string `validate:"omitempty,creative_type"`
	MediaURL       string `validate:"omitempty,url"`
	DestinationURL string `validate:"required,url"`
	Status         string `validate:"omitempty,status"`
}

type TopicTargeting struct {
	TopicID        int32   `validate:"required,gt=0"`
	RelevanceScore float64 `validate:"gte=0,lte=1"`
}

type EntityTargeting struct {
	EntityID   string `validate:"required,min=1"`
	EntityType string `validate:"required,oneof=brand person organization product"`
}

type CampaignResponse struct {
	Advertiser db.Advertiser
	Campaign   db.Campaign
	AdSet      db.AdSet
	Ad         db.Ad
	Targeting  TargetingResponse
}

type TargetingResponse struct {
	Keywords  []db.AdTargetingKeyword
	Topics    []db.AdTargetingTopic
	Entities  []db.AdTargetingEntity
	Countries []db.AdTargetingCountry
}

func (s *CampaignService) CreateCampaignWithDependencies(ctx context.Context,
	req CreateCampaignRequest) (*CampaignResponse, error) {
	if err := s.validateRequest(req); err != nil {
		return nil, fmt.Errorf("validation failed: %w", err)
	}

	var response CampaignResponse

	// Execute in transaction
	txStart := time.Now()
	tx, err := s.db.BeginTx(ctx, &sql.TxOptions{
		Isolation: sql.LevelReadCommitted,
	})
	if err != nil {
		observability.RecordDBQuery(ctx, "create_campaign_tx", time.Since(txStart), err)
		return nil, fmt.Errorf("Failed to begin transaction: %w", err)
	}
	defer func() {
		if p := recover(); p != nil {
			_ = tx.Rollback()
			panic(p)
		} else if err != nil {
			_ = tx.Rollback()
		}
	}()

	// Create queries with transaction
	qtx := s.queries.WithTx(tx)

	endDate := sql.NullTime{}
	if req.Campaign.EndDate != nil {
		endDate = sql.NullTime{Time: *req.Campaign.EndDate, Valid: true}
	}

	campaign, err := qtx.CreateCampaign(ctx, db.CreateCampaignParams{
		AdvertiserID: sql.NullInt32{Int32: req.AdvertiserID, Valid: true},
		Name:         req.Campaign.Name,
		Status:       req.Campaign.Status,
		TotalBudget:  sql.NullInt64{Int64: req.Campaign.TotalBudgetCents, Valid: true},
		StartDate:    req.Campaign.StartDate,
		EndDate:      endDate,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to create campaign: %w", err)
	}
	response.Campaign = campaign

	adSet, err := qtx.CreateAdSet(ctx, db.CreateAdSetParams{
		CampaignID:       sql.NullInt32{Int32: campaign.ID, Valid: true},
		Name:             sql.NullString{String: req.AdSet.Name, Valid: true},
		BidAmountCents:   sql.NullInt64{Int64: req.AdSet.BidAmountCents, Valid: true},
		DailyBudgetCents: sql.NullInt64{Int64: req.AdSet.DailyBudgetCents, Valid: true},
		PricingModel:     sql.NullString{String: req.AdSet.PricingModel, Valid: true},
	})
	if err != nil {
		return nil, fmt.Errorf("failed to create ad set: %w", err)
	}
	response.AdSet = adSet

	// 4. Create Ad
	ad, err := qtx.CreateAd(ctx, db.CreateAdParams{
		AdSetID:        sql.NullInt32{Int32: adSet.ID, Valid: true},
		Headline:       sql.NullString{String: req.Ad.Headline, Valid: true},
		Description:    sql.NullString{String: req.Ad.Description, Valid: true},
		CreativeType:   sql.NullString{String: req.Ad.CreativeType, Valid: true},
		MediaUrl:       sql.NullString{String: req.Ad.MediaURL, Valid: true},
		DestinationUrl: sql.NullString{String: req.Ad.DestinationURL, Valid: true},
		Status:         req.Ad.Status,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to create ad: %w", err)
	}
	response.Ad = ad

	// 5. Create Targeting - Keywords (deduplicate by keyword to avoid unique constraint violations)
	seenKeywords := make(map[string]bool)
	for _, keyword := range req.TargetingKeywords {
		if seenKeywords[keyword] {
			continue
		}
		seenKeywords[keyword] = true
		kw, err := qtx.CreateAdTargetingKeyword(ctx, db.CreateAdTargetingKeywordParams{
			AdID:           sql.NullInt32{Int32: ad.ID, Valid: true},
			Keyword:        keyword,
			RelevanceScore: sql.NullString{String: "1.0", Valid: true},
		})
		if err != nil {
			return nil, fmt.Errorf("failed to create keyword targeting: %w", err)
		}
		response.Targeting.Keywords = append(response.Targeting.Keywords, kw)
	}

	// 6. Create Targeting - Topics (deduplicate by topic ID to avoid unique constraint violations)
	seenTopics := make(map[int32]bool)
	for _, topic := range req.TargetingTopics {
		if seenTopics[topic.TopicID] {
			continue
		}
		seenTopics[topic.TopicID] = true
		t, err := qtx.CreateAdTargetingTopic(ctx, db.CreateAdTargetingTopicParams{
			AdID:           sql.NullInt32{Int32: ad.ID, Valid: true},
			TopicID:        topic.TopicID,
			RelevanceScore: sql.NullString{String: fmt.Sprintf("%.2f", topic.RelevanceScore), Valid: true},
		})
		if err != nil {
			return nil, fmt.Errorf("failed to create topic targeting: %w", err)
		}
		response.Targeting.Topics = append(response.Targeting.Topics, t)
	}

	// 7. Create Targeting - Entities (deduplicate by entity_id+entity_type to avoid unique constraint violations)
	type entityKey struct {
		id    string
		eType string
	}
	seenEntities := make(map[entityKey]bool)
	for _, entity := range req.TargetingEntities {
		entityID := strings.ToLower(entity.EntityID)
		entityName := entity.EntityID
		key := entityKey{id: entityID, eType: entity.EntityType}
		if seenEntities[key] {
			continue
		}
		seenEntities[key] = true

		_, err := tx.ExecContext(ctx, `
			INSERT INTO entities (id, name)
			VALUES ($1, $2)
			ON CONFLICT (id) DO NOTHING
		`, entityID, entityName)
		if err != nil {
			return nil, fmt.Errorf("failed to insert entity: %w", err)
		}

		e, err := qtx.CreateAdTargetingEntity(ctx, db.CreateAdTargetingEntityParams{
			AdID:       sql.NullInt32{Int32: ad.ID, Valid: true},
			EntityID:   entityID,
			EntityType: entity.EntityType,
		})
		if err != nil {
			return nil, fmt.Errorf("failed to create entity targeting: %w", err)
		}
		response.Targeting.Entities = append(response.Targeting.Entities, e)
	}

	// 8. Create Targeting - Countries
	for _, country := range req.TargetingCountries {
		c, err := qtx.CreateAdTargetingCountry(ctx, db.CreateAdTargetingCountryParams{
			AdID:           sql.NullInt32{Int32: ad.ID, Valid: true},
			CountryIsoCode: country,
		})
		if err != nil {
			return nil, fmt.Errorf("failed to create country targeting: %w", err)
		}
		response.Targeting.Countries = append(response.Targeting.Countries, c)
	}

	// 9. Create Targeting - Devices
	for _, device := range req.TargetingDevices {
		d, err := qtx.CreateAdTargetingDevice(ctx, db.CreateAdTargetingDeviceParams{
			AdID:       sql.NullInt32{Int32: ad.ID, Valid: true},
			DeviceType: device,
		})
		if err != nil {
			return nil, fmt.Errorf("failed to create device targeting: %w", err)
		}
		// Note: we don't add to response.Targeting as it doesn't have Devices field yet
		_ = d // Acknowledge we're not using the result
	}

	// Commit transaction
	if err := tx.Commit(); err != nil {
		observability.RecordDBQuery(ctx, "create_campaign_tx", time.Since(txStart), err)
		return nil, fmt.Errorf("failed to commit transaction: %w", err)
	}

	observability.RecordDBQuery(ctx, "create_campaign_tx", time.Since(txStart), nil)

	go func() {
		msg := publisher.AdAnalyzeMessage{
			BaseMessage: publisher.BaseMessage{Timestamp: time.Now().Unix()},
			AdID:        ad.ID,
			CampaignID:  campaign.ID,
			Action:      "created",
		}

		if err := s.publisher.Publish(msg); err != nil {
			observability.Error(ctx, "Failed to publish ad to stream after retries",
				"ad_id", ad.ID, "error", err)
		} else {
			observability.Info(ctx, "Ad queued for analysis", "ad_id", ad.ID)
		}
	}()

	s.SetCache(response)

	return &response, nil
}

func (s *CampaignService) validateRequest(req CreateCampaignRequest) error {
	if err := validation.Validate(req); err != nil {
		messages := validation.FormatValidationErrors(err)
		return fmt.Errorf("validation failed: %s", strings.Join(messages, "; "))
	}

	if req.Campaign.Status == "" {
		req.Campaign.Status = string(models.StatusActive)
	}
	if req.Ad.Status == "" {
		req.Ad.Status = string(models.StatusActive)
	}
	if req.Ad.CreativeType == "" {
		req.Ad.CreativeType = string(models.CreativeTypeBanner)
	}

	return nil
}

func (s *CampaignService) SetCache(response CampaignResponse) {
	ctx := context.Background()
	campaignID := fmt.Sprintf("%d", response.Campaign.ID)
	key := fmt.Sprintf("campaign:%s:state", campaignID)

	// Calculate daily budget from ad set
	dailyBudget := "0.00"
	if response.AdSet.DailyBudgetCents.Valid {
		dailyBudget = fmt.Sprintf("%.2f", float64(response.AdSet.DailyBudgetCents.Int64)/100)
	}

	// Calculate total budget
	totalBudget := "0.00"
	if response.Campaign.TotalBudget.Valid {
		totalBudget = fmt.Sprintf("%.2f", float64(response.Campaign.TotalBudget.Int64)/100)
	}

	// Get end time
	endTime := int64(0)
	if response.Campaign.EndDate.Valid {
		endTime = response.Campaign.EndDate.Time.Unix()
	}

	// Get advertiser ID
	advertiserID := ""
	if response.Campaign.AdvertiserID.Valid {
		advertiserID = fmt.Sprintf("%d", response.Campaign.AdvertiserID.Int32)
	}

	now := time.Now().Unix()

	state := map[string]interface{}{
		"campaign_id":         campaignID,
		"advertiser_id":       advertiserID,
		"total_budget":        totalBudget,
		"daily_budget":        dailyBudget,
		"start_time":          response.Campaign.StartDate.Unix(),
		"end_time":            endTime,
		"status":              response.Campaign.Status,
		"current_multiplier":  1.0,
		"previous_multiplier": 1.0,
		"cumulative_errors":   0.0,
		"created_at":          now,
		"updated_at":          now,
	}

	if err := s.redisClient.HSet(ctx, key, state).Err(); err != nil {
		observability.Error(ctx, "Failed to set campaign state cache", "campaign_id", campaignID, "error", err)
		return
	}

	if err := s.redisClient.SAdd(ctx, "active_campaigns", campaignID).Err(); err != nil {
		observability.Error(ctx, "Failed to add campaign to active campaigns set", "campaign_id", campaignID, "error", err)
	}

	observability.Debug(ctx, "Campaign state cached", "campaign_id", campaignID)
}
