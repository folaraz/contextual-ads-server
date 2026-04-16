package models

import "time"

type Strategy int

const (
	CPM Strategy = iota
	CPC
)

type Ad struct {
	AdID             int32      `json:"ad_id"`
	AdSetID          int32      `json:"ad_set_id"`
	Headline         string     `json:"headline"`
	Description      string     `json:"description"`
	CreativeType     string     `json:"creative_type"`
	MediaURL         string     `json:"media_url"`
	DestinationURL   string     `json:"destination_url"`
	BidAmountCents   int64      `json:"bid_amount_cents"`
	DailyBudgetCents int64      `json:"daily_budget_cents"`
	PricingModel     Strategy   `json:"pricing_model"`
	Status           string     `json:"status"`
	CampaignID       int32      `json:"campaign_id"`
	CampaignStatus   string     `json:"campaign_status"`
	CreatedAt        time.Time  `json:"created_at"`
	UpdatedAt        time.Time  `json:"updated_at"`
	StartDate        time.Time  `json:"start_date"`
	EndDate          *time.Time `json:"end_date,omitempty"`

	// Targeting criteria
	Keywords  []KeywordTarget `json:"keywords"`
	Topics    []TopicTarget   `json:"topics"`
	Entities  []EntityTarget  `json:"entities"`
	Countries []CountryTarget `json:"countries"`
	Devices   []DeviceTarget  `json:"devices"`
}

type KeywordTarget struct {
	Keyword        string  `json:"keyword"`
	RelevanceScore float64 `json:"relevance_score"`
}

type TopicTarget struct {
	TopicID        int32   `json:"topic_id"`
	Tier           int     `json:"tier"`
	RelevanceScore float64 `json:"relevance_score"`
}

type EntityTarget struct {
	EntityID   string `json:"entity_id"`
	EntityType string `json:"entity_type"`
}

type CountryTarget struct {
	CountryISOCode string `json:"country_iso_code"`
}

type DeviceTarget struct {
	DeviceType string `json:"device_type"` // mobile, desktop, tablet
}

type AdContext struct {
	Keywords map[string]float64 `json:"keywords"` // {"food": 1.0, "healthy": 1.0}
	Entities map[string]string  `json:"entities"` // todo: still need to solve the llm integration for entity extraction
	//Topics    map[string]Topic   `json:"topics"`    // iab_id -> Topic
	Embedding []float64 `json:"embedding"`
}
