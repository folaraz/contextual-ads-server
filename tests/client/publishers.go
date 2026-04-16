package client

import (
	"encoding/json"
	"fmt"
	"net/http"
)

type Publisher struct {
	ID        int32  `json:"id"`
	Name      string `json:"name"`
	Domain    string `json:"domain"`
	Email     string `json:"email,omitempty"`
	CreatedAt string `json:"created_at,omitempty"`
}

type CreatePublisherRequest struct {
	Name   string `json:"name"`
	Domain string `json:"domain"`
	Email  string `json:"email,omitempty"`
}

func (c *Client) CreatePublisher(req CreatePublisherRequest) (*Publisher, error) {
	resp, statusCode, err := c.Post("/api/publishers", req)
	if err != nil {
		return nil, err
	}

	if statusCode != http.StatusCreated {
		return nil, fmt.Errorf("failed to create publisher: %s (status %d)", resp.Message, statusCode)
	}

	var publisher Publisher
	if err := json.Unmarshal(resp.Data, &publisher); err != nil {
		return nil, fmt.Errorf("failed to parse publisher response: %w", err)
	}

	return &publisher, nil
}

func (c *Client) ListPublishers() ([]Publisher, error) {
	resp, statusCode, err := c.Get("/api/publishers")
	if err != nil {
		return nil, err
	}

	if statusCode != http.StatusOK {
		return nil, fmt.Errorf("failed to list publishers: %s (status %d)", resp.Message, statusCode)
	}

	var publishers []Publisher
	if err := json.Unmarshal(resp.Data, &publishers); err != nil {
		return nil, fmt.Errorf("failed to parse publishers response: %w", err)
	}

	return publishers, nil
}

func (c *Client) GetPublisher(id int32) (*Publisher, error) {
	resp, statusCode, err := c.Get(fmt.Sprintf("/api/publishers/%d", id))
	if err != nil {
		return nil, err
	}

	if statusCode == http.StatusNotFound {
		return nil, fmt.Errorf("publisher %d not found", id)
	}

	if statusCode != http.StatusOK {
		return nil, fmt.Errorf("failed to get publisher: %s (status %d)", resp.Message, statusCode)
	}

	var publisher Publisher
	if err := json.Unmarshal(resp.Data, &publisher); err != nil {
		return nil, fmt.Errorf("failed to parse publisher response: %w", err)
	}

	return &publisher, nil
}
