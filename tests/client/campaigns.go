package client

import (
	"encoding/json"
	"fmt"
	"net/http"
)

type Campaign struct {
	ID      int32 `json:"campaign_id"`
	AdSetID int32 `json:"ad_set_id"`
	AdID    int32 `json:"ad_id"`
}

type CampaignInput struct {
	Name      string  `json:"name"`
	Status    string  `json:"status,omitempty"`
	Budget    float64 `json:"budget"`
	Currency  string  `json:"currency,omitempty"`
	StartDate string  `json:"start_date"`
	EndDate   string  `json:"end_date,omitempty"`
}

type AdSetInput struct {
	Name         string  `json:"name,omitempty"`
	BidAmount    float64 `json:"bid_amount"`
	DailyBudget  float64 `json:"daily_budget"`
	PricingModel string  `json:"pricing_model"`
}

type CreativeInput struct {
	Headline       string `json:"headline"`
	Description    string `json:"description"`
	ImageURL       string `json:"image_url,omitempty"`
	CallToAction   string `json:"call_to_action,omitempty"`
	LandingPageURL string `json:"landing_page_url"`
	Status         string `json:"status,omitempty"`
	CreativeType   string `json:"creative_type,omitempty"`
}

type EntityInput struct {
	Type string `json:"type"`
	Name string `json:"name"`
}

type TargetingInput struct {
	Keywords  []string      `json:"keywords,omitempty"`
	Topics    []int32       `json:"topics,omitempty"`
	Entities  []EntityInput `json:"entities,omitempty"`
	Countries []string      `json:"countries,omitempty"`
	Devices   []string      `json:"devices,omitempty"`
}

type CreateCampaignRequest struct {
	AdvertiserID int32          `json:"advertiser_id"`
	Campaign     CampaignInput  `json:"campaign"`
	AdSet        AdSetInput     `json:"ad_set"`
	Creative     CreativeInput  `json:"creative"`
	Targeting    TargetingInput `json:"targeting"`
}

type CreateCampaignResponse struct {
	CampaignID int32 `json:"campaign_id"`
	AdSetID    int32 `json:"ad_set_id"`
	AdID       int32 `json:"ad_id"`
}

func (c *Client) CreateCampaign(req CreateCampaignRequest) (*CreateCampaignResponse, error) {
	resp, statusCode, err := c.Post("/api/campaigns", req)
	if err != nil {
		return nil, err
	}

	if statusCode != http.StatusCreated {
		return nil, fmt.Errorf("failed to create campaign: %s (status %d)", resp.Message, statusCode)
	}

	var result CreateCampaignResponse
	if err := json.Unmarshal(resp.Data, &result); err != nil {
		return nil, fmt.Errorf("failed to parse campaign response: %w", err)
	}

	return &result, nil
}

func (c *Client) ListCampaigns() ([]map[string]interface{}, error) {
	resp, statusCode, err := c.Get("/api/campaigns")
	if err != nil {
		return nil, err
	}

	if statusCode != http.StatusOK {
		return nil, fmt.Errorf("failed to list campaigns: %s (status %d)", resp.Message, statusCode)
	}

	var campaigns []map[string]interface{}
	if err := json.Unmarshal(resp.Data, &campaigns); err != nil {
		return nil, fmt.Errorf("failed to parse campaigns response: %w", err)
	}

	return campaigns, nil
}

func (c *Client) GetCampaign(id int32) (map[string]interface{}, error) {
	resp, statusCode, err := c.Get(fmt.Sprintf("/api/campaigns/%d", id))
	if err != nil {
		return nil, err
	}

	if statusCode == http.StatusNotFound {
		return nil, fmt.Errorf("campaign %d not found", id)
	}

	if statusCode != http.StatusOK {
		return nil, fmt.Errorf("failed to get campaign: %s (status %d)", resp.Message, statusCode)
	}

	var campaign map[string]interface{}
	if err := json.Unmarshal(resp.Data, &campaign); err != nil {
		return nil, fmt.Errorf("failed to parse campaign response: %w", err)
	}

	return campaign, nil
}
