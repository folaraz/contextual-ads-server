package client

import (
	"encoding/json"
	"fmt"
	"net/http"
)

type AdServeRequest struct {
	PublisherID string      `json:"publisherId"`
	Context     AdContext   `json:"context"`
	Device      DeviceInfo  `json:"device"`
	Meta        RequestMeta `json:"meta"`
}

type AdContext struct {
	URL         string   `json:"url"`
	Keywords    []string `json:"keywords,omitempty"`
	Title       string   `json:"title,omitempty"`
	Description string   `json:"description,omitempty"`
}

type DeviceInfo struct {
	Type      string `json:"type"`
	UserAgent string `json:"userAgent,omitempty"`
	Language  string `json:"language,omitempty"`
}

type RequestMeta struct {
	Timestamp int64 `json:"timestamp,omitempty"`
}

type AdServeResponse struct {
	AdID          int32  `json:"ad_id"`
	AuctionID     string `json:"auction_id,omitempty"`
	PublisherID   string `json:"publisher_id"`
	MediaURL      string `json:"media_url,omitempty"`
	Headline      string `json:"headline,omitempty"`
	Description   string `json:"description,omitempty"`
	ClickURL      string `json:"click_url,omitempty"`
	ImpressionURL string `json:"impression_url"`
	PricingModel  string `json:"pricing_model"`
	PriceCents    int64  `json:"price_cents"`

	Ad *ServedAd `json:"-"`
}

type ServedAd struct {
	ID             int32   `json:"id"`
	CampaignID     int32   `json:"campaign_id"`
	Headline       string  `json:"headline"`
	Description    string  `json:"description"`
	ImageURL       string  `json:"image_url"`
	CallToAction   string  `json:"call_to_action"`
	LandingPageURL string  `json:"landing_page_url"`
	BidAmount      float64 `json:"bid_amount"`
	PricingModel   string  `json:"pricing_model"`
}

func (c *Client) ServeAd(req AdServeRequest, opts ...RequestOption) (*AdServeResponse, error) {
	resp, statusCode, err := c.Post("/api/ads/serve", req, opts...)
	if err != nil {
		if statusCode == http.StatusNoContent {
			return nil, fmt.Errorf("no content: no ad available (204)")
		}
		return nil, err
	}

	if statusCode == http.StatusNoContent {
		return nil, fmt.Errorf("no content: no ad available (204)")
	}

	if statusCode != http.StatusOK {
		return nil, fmt.Errorf("failed to serve ad: %s (status %d)", resp.Message, statusCode)
	}

	var result AdServeResponse
	if resp.Data != nil && len(resp.Data) > 0 {
		if err := json.Unmarshal(resp.Data, &result); err != nil {
			return nil, fmt.Errorf("failed to parse ad serve response: %w", err)
		}
	}

	if result.AdID > 0 {
		result.Ad = &ServedAd{
			ID:           result.AdID,
			Headline:     result.Headline,
			Description:  result.Description,
			ImageURL:     result.MediaURL,
			PricingModel: result.PricingModel,
		}
	}

	return &result, nil
}

func (c *Client) ServeAdWithIP(req AdServeRequest, ip string) (*AdServeResponse, error) {
	return c.ServeAd(req, WithHeader("X-Forwarded-For", ip))
}
