package client

import (
	"fmt"
	"net/http"
)

func (c *Client) TrackImpression(impressionURL string, opts ...RequestOption) error {
	if impressionURL == "" {
		return fmt.Errorf("impression URL is empty")
	}

	if impressionURL[0] == '/' {
		impressionURL = c.baseURL + impressionURL
	}

	req, err := http.NewRequest(http.MethodPost, impressionURL, nil)
	if err != nil {
		return fmt.Errorf("failed to create impression request: %w", err)
	}

	req.Header.Set("Accept", "application/json")
	req.Header.Set("Content-Type", "application/json")

	for _, opt := range opts {
		opt(req)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("impression request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusNoContent {
		return fmt.Errorf("impression tracking returned status %d", resp.StatusCode)
	}

	return nil
}

func (c *Client) TrackClick(clickURL string, opts ...RequestOption) error {
	if clickURL == "" {
		return fmt.Errorf("click URL is empty")
	}

	if clickURL[0] == '/' {
		clickURL = c.baseURL + clickURL
	}

	req, err := http.NewRequest(http.MethodGet, clickURL, nil)
	if err != nil {
		return fmt.Errorf("failed to create click request: %w", err)
	}

	for _, opt := range opts {
		opt(req)
	}

	client := &http.Client{
		CheckRedirect: func(req *http.Request, via []*http.Request) error {
			return http.ErrUseLastResponse
		},
		Timeout: c.httpClient.Timeout,
	}

	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("click request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusFound && resp.StatusCode != http.StatusNoContent {
		return fmt.Errorf("click tracking returned status %d", resp.StatusCode)
	}

	return nil
}
