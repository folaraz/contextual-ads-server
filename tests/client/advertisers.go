package client

import (
	"encoding/json"
	"fmt"
	"net/http"
)

type Advertiser struct {
	ID      int32  `json:"id"`
	Name    string `json:"name"`
	Website string `json:"website,omitempty"`
}

type CreateAdvertiserRequest struct {
	Name    string `json:"name"`
	Website string `json:"website,omitempty"`
}

func (c *Client) CreateAdvertiser(req CreateAdvertiserRequest) (*Advertiser, error) {
	resp, statusCode, err := c.Post("/api/advertisers", req)
	if err != nil {
		return nil, err
	}

	if statusCode != http.StatusCreated {
		return nil, fmt.Errorf("failed to create advertiser: %s (status %d)", resp.Message, statusCode)
	}

	var advertiser Advertiser
	if err := json.Unmarshal(resp.Data, &advertiser); err != nil {
		return nil, fmt.Errorf("failed to parse advertiser response: %w", err)
	}

	return &advertiser, nil
}

func (c *Client) ListAdvertisers() ([]Advertiser, error) {
	resp, statusCode, err := c.Get("/api/advertisers")
	if err != nil {
		return nil, err
	}

	if statusCode != http.StatusOK {
		return nil, fmt.Errorf("failed to list advertisers: %s (status %d)", resp.Message, statusCode)
	}

	var advertisers []Advertiser
	if err := json.Unmarshal(resp.Data, &advertisers); err != nil {
		return nil, fmt.Errorf("failed to parse advertisers response: %w", err)
	}

	return advertisers, nil
}

func (c *Client) GetAdvertiser(id int32) (*Advertiser, error) {
	resp, statusCode, err := c.Get(fmt.Sprintf("/api/advertisers/%d", id))
	if err != nil {
		return nil, err
	}

	if statusCode == http.StatusNotFound {
		return nil, fmt.Errorf("advertiser %d not found", id)
	}

	if statusCode != http.StatusOK {
		return nil, fmt.Errorf("failed to get advertiser: %s (status %d)", resp.Message, statusCode)
	}

	var advertiser Advertiser
	if err := json.Unmarshal(resp.Data, &advertiser); err != nil {
		return nil, fmt.Errorf("failed to parse advertiser response: %w", err)
	}

	return &advertiser, nil
}
