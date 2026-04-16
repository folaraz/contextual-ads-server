package fixtures

import (
	"encoding/json"
	"fmt"
	"math/rand"
	"os"
	"path/filepath"
	"strconv"
	"time"

	"github.com/folaraz/contextual-ads-server/internal/models"
)

var Categories = Industries

type GeneratedAd struct {
	Ad       models.Ad
	Industry string
}

type inventoryAd struct {
	ID         string `json:"id"`
	Advertiser struct {
		Name   string  `json:"name"`
		Budget float64 `json:"budget"`
	} `json:"advertiser"`
	Campaign struct {
		Name string `json:"name"`
	} `json:"campaign"`
	Creative struct {
		Headline       string `json:"headline"`
		Description    string `json:"description"`
		ImageURL       string `json:"image_url"`
		CallToAction   string `json:"call_to_action"`
		LandingPageURL string `json:"landing_page_url"`
	} `json:"creative"`
	Targeting struct {
		Keywords []string `json:"keywords"`
		Topics   []struct {
			Name  string `json:"name"`
			IabID string `json:"iab_id"`
			Tier  int    `json:"tier"`
		} `json:"topics"`
		Entities  []string `json:"entities"`
		Countries []string `json:"countries"`
		Languages []string `json:"languages"`
	} `json:"targeting"`
	ContentCategory string  `json:"content_category"`
	DailyBudget     float64 `json:"daily_budget"`
	RemainingBudget float64 `json:"remaining_budget"`
	Status          string  `json:"status"`
	StartDate       string  `json:"start_date"`
	EndDate         string  `json:"end_date"`
	CreatedAt       string  `json:"created_at"`
	Impressions     int64   `json:"impressions"`
	Clicks          int64   `json:"clicks"`
	Spend           float64 `json:"spend"`
}

const adsPerIndustry = 125

func LoadAds() ([]GeneratedAd, error) {
	realAds, err := loadRealAds()
	if err != nil {
		return nil, fmt.Errorf("loading real ads: %w", err)
	}

	realCountByIndustry := make(map[string]int)
	for _, ga := range realAds {
		realCountByIndustry[ga.Industry]++
	}

	rng := rand.New(rand.NewSource(42))
	nextID := int32(1000)

	var syntheticAds []GeneratedAd
	for _, industry := range Industries {
		tmpl, ok := IndustryTemplates[industry]
		if !ok {
			continue
		}
		realCount := realCountByIndustry[industry]
		needed := adsPerIndustry - realCount
		if needed <= 0 {
			continue
		}

		for i := 0; i < needed; i++ {
			ad := generateSyntheticAd(rng, nextID, tmpl)
			syntheticAds = append(syntheticAds, GeneratedAd{
				Ad:       ad,
				Industry: industry,
			})
			nextID++
		}
	}

	all := make([]GeneratedAd, 0, len(realAds)+len(syntheticAds))
	all = append(all, realAds...)
	all = append(all, syntheticAds...)

	return all, nil
}

func loadRealAds() ([]GeneratedAd, error) {
	dataDir := findDataDir()
	data, err := os.ReadFile(filepath.Join(dataDir, "ads_inventory.json"))
	if err != nil {
		return nil, fmt.Errorf("reading ads inventory: %w", err)
	}

	var inventory []inventoryAd
	if err := json.Unmarshal(data, &inventory); err != nil {
		return nil, fmt.Errorf("parsing ads inventory: %w", err)
	}

	ads := make([]GeneratedAd, 0, len(inventory))
	for _, inv := range inventory {
		ad, err := inventoryToAd(inv)
		if err != nil {
			continue
		}

		industry := mapContentCategoryToIndustry(inv.ContentCategory)

		ads = append(ads, GeneratedAd{
			Ad:       ad,
			Industry: industry,
		})
	}

	return ads, nil
}

func mapContentCategoryToIndustry(category string) string {
	if industry, ok := ContentCategoryToIndustry[category]; ok {
		return industry
	}
	return category
}

func generateSyntheticAd(rng *rand.Rand, adID int32, tmpl IndustryTemplate) models.Ad {
	numKeywords := 5 + rng.Intn(4)
	if numKeywords > len(tmpl.Keywords) {
		numKeywords = len(tmpl.Keywords)
	}
	kwIndices := rng.Perm(len(tmpl.Keywords))[:numKeywords]
	keywords := make([]models.KeywordTarget, numKeywords)
	for i, idx := range kwIndices {
		keywords[i] = models.KeywordTarget{
			Keyword:        tmpl.Keywords[idx],
			RelevanceScore: 0.7 + rng.Float64()*0.3,
		}
	}

	numTopics := 1
	if len(tmpl.TopicIDs) > 1 && rng.Float64() > 0.5 {
		numTopics = 2
	}
	topics := make([]models.TopicTarget, numTopics)
	for i := 0; i < numTopics && i < len(tmpl.TopicIDs); i++ {
		topicID, _ := strconv.Atoi(tmpl.TopicIDs[i])
		topics[i] = models.TopicTarget{
			TopicID:        int32(topicID),
			Tier:           1 + rng.Intn(3),
			RelevanceScore: 0.6 + rng.Float64()*0.4,
		}
	}

	numEntities := 1 + rng.Intn(3)
	if numEntities > len(tmpl.Entities) {
		numEntities = len(tmpl.Entities)
	}
	entIndices := rng.Perm(len(tmpl.Entities))[:numEntities]
	entities := make([]models.EntityTarget, numEntities)
	for i, idx := range entIndices {
		entities[i] = models.EntityTarget{
			EntityID:   tmpl.Entities[idx],
			EntityType: tmpl.EntityTypes[idx],
		}
	}

	pricingModel := models.CPM
	var bidAmountCents int64
	if rng.Float64() < 0.3 {
		pricingModel = models.CPC
		bidAmountCents = 50 + int64(rng.Intn(451))
	} else {
		bidAmountCents = 100 + int64(rng.Intn(1401))
	}

	dailyBudgetCents := int64(5000 + rng.Intn(45001))

	headline := tmpl.HeadlineTemplates[rng.Intn(len(tmpl.HeadlineTemplates))]
	description := tmpl.DescriptionTemplates[rng.Intn(len(tmpl.DescriptionTemplates))]

	startDate := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	endDate := startDate.Add(30 * 24 * time.Hour)

	return models.Ad{
		AdID:             adID,
		AdSetID:          adID,
		Headline:         headline,
		Description:      description,
		CreativeType:     "display",
		MediaURL:         fmt.Sprintf("https://cdn.example.com/ads/%d.jpg", adID),
		DestinationURL:   fmt.Sprintf("https://example.com/landing/%s/%d", tmpl.Industry, adID),
		BidAmountCents:   bidAmountCents,
		DailyBudgetCents: dailyBudgetCents,
		PricingModel:     pricingModel,
		Status:           "ACTIVE",
		CampaignID:       adID,
		CampaignStatus:   "ACTIVE",
		CreatedAt:        startDate,
		UpdatedAt:        startDate,
		StartDate:        startDate,
		EndDate:          &endDate,
		Keywords:         keywords,
		Topics:           topics,
		Entities:         entities,
		Countries:        []models.CountryTarget{{CountryISOCode: "US"}},
		Devices:          []models.DeviceTarget{{DeviceType: "desktop"}, {DeviceType: "mobile"}},
	}
}

func AllAdKeywords(ads []GeneratedAd) []string {
	seen := make(map[string]bool)
	var all []string
	for _, ga := range ads {
		for _, kw := range ga.Ad.Keywords {
			lower := kw.Keyword
			if !seen[lower] {
				seen[lower] = true
				all = append(all, lower)
			}
		}
	}
	return all
}

func inventoryToAd(inv inventoryAd) (models.Ad, error) {
	adID, err := strconv.Atoi(inv.ID)
	if err != nil {
		return models.Ad{}, fmt.Errorf("parsing ad ID %q: %w", inv.ID, err)
	}

	keywords := make([]models.KeywordTarget, len(inv.Targeting.Keywords))
	for i, kw := range inv.Targeting.Keywords {
		keywords[i] = models.KeywordTarget{
			Keyword:        kw,
			RelevanceScore: 1.0,
		}
	}

	topics := make([]models.TopicTarget, len(inv.Targeting.Topics))
	for i, t := range inv.Targeting.Topics {
		topicID, _ := strconv.Atoi(t.IabID)
		topics[i] = models.TopicTarget{
			TopicID:        int32(topicID),
			Tier:           t.Tier,
			RelevanceScore: 0.8,
		}
	}

	entities := make([]models.EntityTarget, len(inv.Targeting.Entities))
	for i, e := range inv.Targeting.Entities {
		entities[i] = models.EntityTarget{
			EntityID:   e,
			EntityType: "BRAND",
		}
	}

	countries := make([]models.CountryTarget, len(inv.Targeting.Countries))
	for i, c := range inv.Targeting.Countries {
		countries[i] = models.CountryTarget{CountryISOCode: c}
	}

	bidAmountCents := int64(inv.DailyBudget * 2)
	if bidAmountCents < 100 {
		bidAmountCents = 100
	}
	if bidAmountCents > 1500 {
		bidAmountCents = 1500
	}

	dailyBudgetCents := int64(inv.DailyBudget * 100)

	startDate, _ := time.Parse("2006-01-02", inv.StartDate)
	endDate, _ := time.Parse("2006-01-02", inv.EndDate)
	createdAt, _ := time.Parse(time.RFC3339, inv.CreatedAt)

	return models.Ad{
		AdID:             int32(adID),
		AdSetID:          int32(adID),
		Headline:         inv.Creative.Headline,
		Description:      inv.Creative.Description,
		CreativeType:     "display",
		MediaURL:         inv.Creative.ImageURL,
		DestinationURL:   inv.Creative.LandingPageURL,
		BidAmountCents:   bidAmountCents,
		DailyBudgetCents: dailyBudgetCents,
		PricingModel:     models.CPM,
		Status:           "ACTIVE",
		CampaignID:       int32(adID),
		CampaignStatus:   "ACTIVE",
		CreatedAt:        createdAt,
		UpdatedAt:        time.Now(),
		StartDate:        startDate,
		EndDate:          &endDate,
		Keywords:         keywords,
		Topics:           topics,
		Entities:         entities,
		Countries:        countries,
		Devices:          []models.DeviceTarget{{DeviceType: "desktop"}, {DeviceType: "mobile"}},
	}, nil
}
