package models

type Strategy int

const (
	CPM Strategy = iota
	CPC
	CPA
)

type Ad struct {
	ID               string     `json:"id"`
	Advertiser       Advertiser `json:"advertiser"`
	Campaign         Campaign   `json:"campaign"`
	Creative         Creative   `json:"creative"`
	Targeting        Targeting  `json:"targeting"`
	AdContext        AdContext  `json:"ad_context"`
	DailyBudget      float64    `json:"daily_budget"`
	RemainingBudget  float64    `json:"remaining_budget"`
	DailyBudgetSpend float64    `json:"daily_budget_spend"`
	BidAmount        float64    `json:"bid_amount"`
	Strategy         Strategy   `json:"strategy"` // e.g., CPC, CPM, CPA
	Status           string     `json:"status"`
	StartDate        string     `json:"start_date"`
	EndDate          string     `json:"end_date"`
	CreatedAt        string     `json:"created_at"`
	Impressions      int        `json:"impressions"`
	Clicks           int        `json:"clicks"`
	Spend            float64    `json:"spend"`
}

type Advertiser struct {
	Name     string  `json:"name"`
	Budget   float64 `json:"budget"`
	Currency string  `json:"currency"`
}

type Campaign struct {
	Name string `json:"name"`
}

type Creative struct {
	Headline     string `json:"headline"`
	Description  string `json:"description"`
	ImageURL     string `json:"image_url"`
	CallToAction string `json:"call_to_action"`
}

type Targeting struct {
	Countries []string `json:"countries"`
	Entities  []string `json:"entities"`
	Keywords  []string `json:"keywords"`
	Languages []string `json:"languages"`
	Topics    []Topic  `json:"topics"`
}

type AdContext struct {
	Keywords  map[string]float64 `json:"keywords"`  // {"food": 1.0, "healthy": 1.0}
	Entities  map[string]string  `json:"entities"`  // todo: still need to solve the llm integration for entity extraction
	Topics    map[string]Topic   `json:"topics"`    // iab_id -> Topic
	Embedding []float64          `json:"embedding"` // [0.015, -0.023, ...]
}

type Topic struct {
	IabID string  `json:"iab_id"`
	Tier  int     `json:"tier"`
	Score float64 `json:"score"`
}
