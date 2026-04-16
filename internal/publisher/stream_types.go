package publisher

import "fmt"

type StreamType string

const (
	StreamTypeAdAnalyze    StreamType = "ad_analyze"
	StreamTypePageAnalyze  StreamType = "page_analyze"
	StreamTypeAdEvent      StreamType = "ad_event"
	StreamTypeAuctionEvent StreamType = "auction"
)

func (s StreamType) String() string {
	return string(s)
}

func (s StreamType) IsValid() bool {
	switch s {
	case StreamTypeAdAnalyze, StreamTypeAdEvent, StreamTypePageAnalyze,
		StreamTypeAuctionEvent:
		return true
	}
	return false
}

func (s StreamType) GetEventType() string {
	if s.IsValid() {
		return string(s)
	}
	return "unknown"
}

type Message interface {
	GetStreamType() StreamType

	ToMap() map[string]interface{}
}

type BaseMessage struct {
	Timestamp int64  `json:"timestamp"`
	EventType string `json:"event_type"`
}

type AdAnalyzeMessage struct {
	BaseMessage
	AdID       int32  `json:"ad_id"`
	CampaignID int32  `json:"campaign_id"`
	Action     string `json:"action"`
}

func (m AdAnalyzeMessage) GetStreamType() StreamType {
	return StreamTypeAdAnalyze
}

func (m AdAnalyzeMessage) ToMap() map[string]interface{} {
	data := map[string]interface{}{
		"ad_id":       m.AdID,
		"campaign_id": m.CampaignID,
		"action":      m.Action,
		"timestamp":   m.Timestamp,
		"event_type":  m.GetStreamType().GetEventType(),
	}
	return data
}

func (m AdAnalyzeMessage) GetKey() string {
	return fmt.Sprintf("ad_%d", m.AdID)
}

type PageAnalyzeMessage struct {
	BaseMessage
	PageUrlHash string `json:"page_url_hash"`
	PageUrl     string `json:"page_url"`
	PublisherID string `json:"publisher_id"`
}

func (m PageAnalyzeMessage) GetStreamType() StreamType {
	return StreamTypePageAnalyze
}

func (m PageAnalyzeMessage) ToMap() map[string]interface{} {
	data := map[string]interface{}{
		"page_url_hash": m.PageUrlHash,
		"page_url":      m.PageUrl,
		"publisher_id":  m.PublisherID,
		"timestamp":     m.Timestamp,
		"event_type":    m.GetStreamType().GetEventType(),
	}
	return data
}

func (m PageAnalyzeMessage) GetKey() string {
	return m.PageUrlHash
}

type AdEventType string

const (
	AdEventImpression AdEventType = "impression"
	AdEventClick      AdEventType = "click"
)

type AdEventMessage struct {
	BaseMessage
	EventType   AdEventType `json:"event_type"`
	CampaignID  string      `json:"campaign_id"`
	PriceCents  int64       `json:"price_cents"`
	AuctionID   string      `json:"auction_id"`
	AdID        string      `json:"ad_id"`
	ClickURL    string      `json:"click_url,omitempty"`
	PageURL     string      `json:"page_url"`
	PublisherID string      `json:"publisher_id,omitempty"`
	DeviceType  string      `json:"device_type,omitempty"`
	UserAgent   string      `json:"user_agent,omitempty"`
	IPAddress   string      `json:"ip_address,omitempty"`
}

func (m AdEventMessage) GetStreamType() StreamType {
	return StreamTypeAdEvent
}

func (m AdEventMessage) ToMap() map[string]interface{} {
	data := map[string]interface{}{
		"event_type":   string(m.EventType),
		"campaign_id":  m.CampaignID,
		"price_cents":  m.PriceCents,
		"auction_id":   m.AuctionID,
		"ad_id":        m.AdID,
		"page_url":     m.PageURL,
		"publisher_id": m.PublisherID,
		"user_agent":   m.UserAgent,
		"ip_address":   m.IPAddress,
		"timestamp":    m.Timestamp,
	}
	if m.ClickURL != "" {
		data["click_url"] = m.ClickURL
	}
	if m.DeviceType != "" {
		data["device_type"] = m.DeviceType
	}
	return data
}

func (m AdEventMessage) GetKey() string {
	return m.CampaignID
}

type AuctionMessage struct {
	BaseMessage
	AuctionID            string             `json:"auction_id"`
	Candidates           []AuctionCandidate `json:"candidates"`
	Winner               *AuctionCandidate  `json:"winner,omitempty"`
	NumOfCandidates      int                `json:"num_of_candidates"`
	NumFilteredBudget    int                `json:"num_filtered_budget"`
	NumFilteredTargeting int                `json:"num_filtered_targeting"`
	NumEligible          int                `json:"num_eligible"`
	PageURL              string             `json:"page_url"`
	PublisherID          string             `json:"publisher_id,omitempty"`
	DeviceType           string             `json:"device_type,omitempty"`
	UserAgent            string             `json:"user_agent,omitempty"`
	IPAddress            string             `json:"ip_address,omitempty"`
}

type AuctionCandidate struct {
	AdID           int32   `json:"ad_id"`
	CampaignID     int32   `json:"campaign_id"`
	PacingScore    float64 `json:"pacing_score"`
	Similarity     float64 `json:"similarity"`
	QualityScore   float64 `json:"quality_score"`
	NormalizedBid  float64 `json:"normalized_bid"`
	EffectiveBid   float64 `json:"effective_bid"`
	FinalRankScore float64 `json:"final_rank_score"`
}

func (m AuctionMessage) GetStreamType() StreamType {
	return StreamTypeAuctionEvent
}

func (m AuctionMessage) ToMap() map[string]interface{} {
	candidates := make([]map[string]interface{}, len(m.Candidates))
	for i, c := range m.Candidates {
		candidates[i] = map[string]interface{}{
			"ad_id":            c.AdID,
			"campaign_id":      c.CampaignID,
			"pacing_score":     c.PacingScore,
			"similarity":       c.Similarity,
			"quality_score":    c.QualityScore,
			"normalized_bid":   c.NormalizedBid,
			"effective_bid":    c.EffectiveBid,
			"final_rank_score": c.FinalRankScore,
		}
	}

	// Convert winner to map (only if winner exists)
	var winner map[string]interface{}
	if m.Winner != nil {
		winner = map[string]interface{}{
			"ad_id":            m.Winner.AdID,
			"campaign_id":      m.Winner.CampaignID,
			"pacing_score":     m.Winner.PacingScore,
			"similarity":       m.Winner.Similarity,
			"quality_score":    m.Winner.QualityScore,
			"normalized_bid":   m.Winner.NormalizedBid,
			"effective_bid":    m.Winner.EffectiveBid,
			"final_rank_score": m.Winner.FinalRankScore,
		}
	}

	data := map[string]interface{}{
		"auction_id":             m.AuctionID,
		"candidates":             candidates,
		"winner":                 winner,
		"num_of_candidates":      m.NumOfCandidates,
		"num_filtered_budget":    m.NumFilteredBudget,
		"num_filtered_targeting": m.NumFilteredTargeting,
		"num_eligible":           m.NumEligible,
		"page_url":               m.PageURL,
		"publisher_id":           m.PublisherID,
		"user_agent":             m.UserAgent,
		"ip_address":             m.IPAddress,
		"timestamp":              m.Timestamp,
		"event_type":             m.GetStreamType().GetEventType(),
	}
	if m.DeviceType != "" {
		data["device_type"] = m.DeviceType
	}
	return data
}

func (m AuctionMessage) GetKey() string {
	return m.AuctionID
}
