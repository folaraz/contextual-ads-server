package targeting

import (
	"context"
	"database/sql"
	"fmt"
	"strconv"
	"time"

	db "github.com/folaraz/contextual-ads-server/db/sqlc"
	"github.com/folaraz/contextual-ads-server/internal/models"
	"github.com/folaraz/contextual-ads-server/internal/observability"
)

type AdTargetingService struct {
	queries *db.Queries
}

func NewAdTargetingService(database *sql.DB) *AdTargetingService {
	return &AdTargetingService{
		queries: db.New(database),
	}
}

func (s *AdTargetingService) GetAllActiveAds(ctx context.Context) ([]models.Ad, error) {

	dbStart := time.Now()
	ads, err := s.queries.ListAllActiveAdsForIndex(ctx)
	observability.RecordDBQuery(ctx, "list_active_ads", time.Since(dbStart), err)
	if err != nil {
		return nil, fmt.Errorf("failed to list active ads: %w", err)
	}

	if len(ads) == 0 {
		return []models.Ad{}, nil
	}

	adIDs := make([]int32, len(ads))
	for i, ad := range ads {
		adIDs[i] = ad.ID
	}

	keywordsCh := make(chan []db.AdTargetingKeyword, 1)
	topicsCh := make(chan []db.GetAdTargetingTopicsByAdIdsRow, 1)
	entitiesCh := make(chan []db.AdTargetingEntity, 1)
	countriesCh := make(chan []db.AdTargetingCountry, 1)
	devicesCh := make(chan []db.AdTargetingDevice, 1)
	errCh := make(chan error, 5)

	// Fetch keywords
	go func() {
		start := time.Now()
		keywords, err := s.queries.GetAdTargetingKeywordsByAdIds(ctx, adIDs)
		observability.RecordDBQuery(ctx, "get_targeting_keywords", time.Since(start), err)
		if err != nil {
			errCh <- fmt.Errorf("failed to fetch keywords: %w", err)
			return
		}
		keywordsCh <- keywords
	}()

	// Fetch topics
	go func() {
		start := time.Now()
		topics, err := s.queries.GetAdTargetingTopicsByAdIds(ctx, adIDs)
		observability.RecordDBQuery(ctx, "get_targeting_topics", time.Since(start), err)
		if err != nil {
			errCh <- fmt.Errorf("failed to fetch topics: %w", err)
			return
		}
		topicsCh <- topics
	}()

	// Fetch entities
	go func() {
		start := time.Now()
		entities, err := s.queries.GetAdTargetingEntitiesByAdIds(ctx, adIDs)
		observability.RecordDBQuery(ctx, "get_targeting_entities", time.Since(start), err)
		if err != nil {
			errCh <- fmt.Errorf("failed to fetch entities: %w", err)
			return
		}
		entitiesCh <- entities
	}()

	// Fetch countries
	go func() {
		start := time.Now()
		countries, err := s.queries.GetAdTargetingCountriesByAdIds(ctx, adIDs)
		observability.RecordDBQuery(ctx, "get_targeting_countries", time.Since(start), err)
		if err != nil {
			errCh <- fmt.Errorf("failed to fetch countries: %w", err)
			return
		}
		countriesCh <- countries
	}()

	// Fetch devices
	go func() {
		start := time.Now()
		devices, err := s.queries.GetAdTargetingDevicesByAdIds(ctx, adIDs)
		observability.RecordDBQuery(ctx, "get_targeting_devices", time.Since(start), err)
		if err != nil {
			errCh <- fmt.Errorf("failed to fetch devices: %w", err)
			return
		}
		devicesCh <- devices
	}()

	// Wait for all results
	var keywords []db.AdTargetingKeyword
	var topics []db.GetAdTargetingTopicsByAdIdsRow
	var entities []db.AdTargetingEntity
	var countries []db.AdTargetingCountry
	var devices []db.AdTargetingDevice

	for i := 0; i < 5; i++ {
		select {
		case err := <-errCh:
			return nil, err
		case keywords = <-keywordsCh:
		case topics = <-topicsCh:
		case entities = <-entitiesCh:
		case countries = <-countriesCh:
		case devices = <-devicesCh:
		}
	}

	keywordsMap := groupKeywordsByAdID(keywords)
	topicsMap := groupTopicsByAdID(topics)
	entitiesMap := groupEntitiesByAdID(entities)
	countriesMap := groupCountriesByAdID(countries)
	devicesMap := groupDevicesByAdID(devices)

	result := make([]models.Ad, 0, len(ads))
	for _, ad := range ads {
		adTargeting := models.Ad{
			AdID:             ad.ID,
			AdSetID:          nullInt32ToInt32(ad.AdSetID),
			Headline:         nullStringToString(ad.Headline),
			Description:      nullStringToString(ad.Description),
			CreativeType:     nullStringToString(ad.CreativeType),
			MediaURL:         nullStringToString(ad.MediaUrl),
			DestinationURL:   nullStringToString(ad.DestinationUrl),
			Status:           ad.Status,
			CreatedAt:        nullTimeToTime(ad.CreatedAt),
			UpdatedAt:        nullTimeToTime(ad.UpdatedAt),
			CampaignID:       ad.CampaignID,
			CampaignStatus:   ad.CampaignStatus,
			DailyBudgetCents: nullInt64ToInt64(ad.DailyBudgetCents),
			BidAmountCents:   nullInt64ToInt64(ad.BidAmountCents),
			PricingModel:     parsePricingModel(ad.PricingModel),
			StartDate:        ad.StartDate,
			EndDate:          nullTimeToTimePtr(ad.EndDate),
			Keywords:         keywordsMap[ad.ID],
			Topics:           topicsMap[ad.ID],
			Entities:         entitiesMap[ad.ID],
			Countries:        countriesMap[ad.ID],
			Devices:          devicesMap[ad.ID],
		}
		result = append(result, adTargeting)
	}

	return result, nil
}

func (s *AdTargetingService) GetAllAdsChangedSince(ctx context.Context, lastUpdated time.Time) ([]models.Ad, error) {

	dbStart := time.Now()
	ads, err := s.queries.ListChangedAdsForIndex(ctx, sql.NullTime{Time: lastUpdated, Valid: true})
	observability.RecordDBQuery(ctx, "list_changed_ads", time.Since(dbStart), err)
	if err != nil {
		return nil, fmt.Errorf("failed to list active ads: %w", err)
	}

	if len(ads) == 0 {
		return []models.Ad{}, nil
	}

	adIDs := make([]int32, len(ads))
	for i, ad := range ads {
		adIDs[i] = ad.ID
	}

	keywordsCh := make(chan []db.AdTargetingKeyword, 1)
	topicsCh := make(chan []db.GetAdTargetingTopicsByAdIdsRow, 1)
	entitiesCh := make(chan []db.AdTargetingEntity, 1)
	countriesCh := make(chan []db.AdTargetingCountry, 1)
	devicesCh := make(chan []db.AdTargetingDevice, 1)
	errCh := make(chan error, 5)

	// Fetch keywords
	go func() {
		start := time.Now()
		keywords, err := s.queries.GetAdTargetingKeywordsByAdIds(ctx, adIDs)
		observability.RecordDBQuery(ctx, "get_targeting_keywords", time.Since(start), err)
		if err != nil {
			errCh <- fmt.Errorf("failed to fetch keywords: %w", err)
			return
		}
		keywordsCh <- keywords
	}()

	// Fetch topics
	go func() {
		start := time.Now()
		topics, err := s.queries.GetAdTargetingTopicsByAdIds(ctx, adIDs)
		observability.RecordDBQuery(ctx, "get_targeting_topics", time.Since(start), err)
		if err != nil {
			errCh <- fmt.Errorf("failed to fetch topics: %w", err)
			return
		}
		topicsCh <- topics
	}()

	// Fetch entities
	go func() {
		start := time.Now()
		entities, err := s.queries.GetAdTargetingEntitiesByAdIds(ctx, adIDs)
		observability.RecordDBQuery(ctx, "get_targeting_entities", time.Since(start), err)
		if err != nil {
			errCh <- fmt.Errorf("failed to fetch entities: %w", err)
			return
		}
		entitiesCh <- entities
	}()

	// Fetch countries
	go func() {
		start := time.Now()
		countries, err := s.queries.GetAdTargetingCountriesByAdIds(ctx, adIDs)
		observability.RecordDBQuery(ctx, "get_targeting_countries", time.Since(start), err)
		if err != nil {
			errCh <- fmt.Errorf("failed to fetch countries: %w", err)
			return
		}
		countriesCh <- countries
	}()

	// Fetch devices
	go func() {
		start := time.Now()
		devices, err := s.queries.GetAdTargetingDevicesByAdIds(ctx, adIDs)
		observability.RecordDBQuery(ctx, "get_targeting_devices", time.Since(start), err)
		if err != nil {
			errCh <- fmt.Errorf("failed to fetch devices: %w", err)
			return
		}
		devicesCh <- devices
	}()

	// Wait for all results
	var keywords []db.AdTargetingKeyword
	var topics []db.GetAdTargetingTopicsByAdIdsRow
	var entities []db.AdTargetingEntity
	var countries []db.AdTargetingCountry
	var devices []db.AdTargetingDevice

	for i := 0; i < 5; i++ {
		select {
		case err := <-errCh:
			return nil, err
		case keywords = <-keywordsCh:
		case topics = <-topicsCh:
		case entities = <-entitiesCh:
		case countries = <-countriesCh:
		case devices = <-devicesCh:
		}
	}

	keywordsMap := groupKeywordsByAdID(keywords)
	topicsMap := groupTopicsByAdID(topics)
	entitiesMap := groupEntitiesByAdID(entities)
	countriesMap := groupCountriesByAdID(countries)
	devicesMap := groupDevicesByAdID(devices)

	result := make([]models.Ad, 0, len(ads))
	for _, ad := range ads {
		adTargeting := models.Ad{
			AdID:             ad.ID,
			AdSetID:          nullInt32ToInt32(ad.AdSetID),
			Headline:         nullStringToString(ad.Headline),
			Description:      nullStringToString(ad.Description),
			CreativeType:     nullStringToString(ad.CreativeType),
			MediaURL:         nullStringToString(ad.MediaUrl),
			DestinationURL:   nullStringToString(ad.DestinationUrl),
			Status:           ad.Status,
			CreatedAt:        nullTimeToTime(ad.CreatedAt),
			UpdatedAt:        nullTimeToTime(ad.UpdatedAt),
			CampaignID:       ad.CampaignID,
			CampaignStatus:   ad.CampaignStatus,
			DailyBudgetCents: nullInt64ToInt64(ad.DailyBudgetCents),
			BidAmountCents:   nullInt64ToInt64(ad.BidAmountCents),
			PricingModel:     parsePricingModel(ad.PricingModel),
			StartDate:        ad.StartDate,
			EndDate:          nullTimeToTimePtr(ad.EndDate),
			Keywords:         keywordsMap[ad.ID],
			Topics:           topicsMap[ad.ID],
			Entities:         entitiesMap[ad.ID],
			Countries:        countriesMap[ad.ID],
			Devices:          devicesMap[ad.ID],
		}
		result = append(result, adTargeting)
	}

	return result, nil
}

func groupKeywordsByAdID(keywords []db.AdTargetingKeyword) map[int32][]models.KeywordTarget {
	result := make(map[int32][]models.KeywordTarget)
	for _, kw := range keywords {
		if !kw.AdID.Valid {
			continue
		}
		adID := kw.AdID.Int32
		result[adID] = append(result[adID], models.KeywordTarget{
			Keyword:        kw.Keyword,
			RelevanceScore: parseRelevanceScore(kw.RelevanceScore),
		})
	}
	return result
}

func groupTopicsByAdID(topics []db.GetAdTargetingTopicsByAdIdsRow) map[int32][]models.TopicTarget {
	result := make(map[int32][]models.TopicTarget)
	for _, topic := range topics {
		if !topic.AdID.Valid {
			continue
		}
		adID := topic.AdID.Int32
		result[adID] = append(result[adID], models.TopicTarget{
			TopicID:        topic.TopicID,
			Tier:           int(topic.Tier),
			RelevanceScore: parseRelevanceScore(topic.RelevanceScore),
		})
	}
	return result
}

func groupEntitiesByAdID(entities []db.AdTargetingEntity) map[int32][]models.EntityTarget {
	result := make(map[int32][]models.EntityTarget)
	for _, entity := range entities {
		if !entity.AdID.Valid {
			continue
		}
		adID := entity.AdID.Int32
		result[adID] = append(result[adID], models.EntityTarget{
			EntityID:   entity.EntityID,
			EntityType: entity.EntityType,
		})
	}
	return result
}

func groupCountriesByAdID(countries []db.AdTargetingCountry) map[int32][]models.CountryTarget {
	result := make(map[int32][]models.CountryTarget)
	for _, country := range countries {
		if !country.AdID.Valid {
			continue
		}
		adID := country.AdID.Int32
		result[adID] = append(result[adID], models.CountryTarget{
			CountryISOCode: country.CountryIsoCode,
		})
	}
	return result
}

func groupDevicesByAdID(devices []db.AdTargetingDevice) map[int32][]models.DeviceTarget {
	result := make(map[int32][]models.DeviceTarget)
	for _, device := range devices {
		if !device.AdID.Valid {
			continue
		}
		adID := device.AdID.Int32
		result[adID] = append(result[adID], models.DeviceTarget{
			DeviceType: device.DeviceType,
		})
	}
	return result
}

func nullStringToString(ns sql.NullString) string {
	if ns.Valid {
		return ns.String
	}
	return ""
}

func nullInt32ToInt32(ni sql.NullInt32) int32 {
	if ni.Valid {
		return ni.Int32
	}
	return 0
}

func nullInt64ToInt64(ni sql.NullInt64) int64 {
	if ni.Valid {
		return ni.Int64
	}
	return 0
}

func nullTimeToTime(nt sql.NullTime) time.Time {
	if nt.Valid {
		return nt.Time
	}
	return time.Time{}
}

func nullTimeToTimePtr(nt sql.NullTime) *time.Time {
	if nt.Valid {
		return &nt.Time
	}
	return nil
}

func parsePricingModel(ns sql.NullString) models.Strategy {
	if !ns.Valid {
		return models.CPM
	}
	switch ns.String {
	case "CPC":
		return models.CPC
	default:
		return models.CPM
	}
}

func parseRelevanceScore(ns sql.NullString) float64 {
	if !ns.Valid {
		return 1.0
	}
	score, err := strconv.ParseFloat(ns.String, 64)
	if err != nil {
		return 1.0
	}
	return score
}
