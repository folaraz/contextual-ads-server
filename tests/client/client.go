package client

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/folaraz/contextual-ads-server/tests/config"
)

type Client struct {
	baseURL    string
	httpClient *http.Client
	verbose    bool
}

func NewClient(cfg *config.Config) *Client {
	return &Client{
		baseURL: cfg.API.BaseURL,
		httpClient: &http.Client{
			Timeout: time.Duration(cfg.API.Timeout) * time.Second,
		},
		verbose: false,
	}
}

func NewClientWithURL(baseURL string, timeout time.Duration) *Client {
	return &Client{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: timeout,
		},
		verbose: false,
	}
}

func (c *Client) SetVerbose(verbose bool) {
	c.verbose = verbose
}

func (c *Client) BaseURL() string {
	return c.baseURL
}

type APIResponse struct {
	Success bool            `json:"success"`
	Message string          `json:"message,omitempty"`
	Data    json.RawMessage `json:"data,omitempty"`
	Errors  []string        `json:"errors,omitempty"`
}

type RequestOption func(*http.Request)

func WithHeader(key, value string) RequestOption {
	return func(r *http.Request) {
		r.Header.Set(key, value)
	}
}

func WithContext(ctx context.Context) RequestOption {
	return func(r *http.Request) {
		*r = *r.WithContext(ctx)
	}
}

func (c *Client) doRequest(method, path string, body interface{}, opts ...RequestOption) (*APIResponse, int, error) {
	url := c.baseURL + path

	var reqBody io.Reader
	if body != nil {
		jsonBody, err := json.Marshal(body)
		if err != nil {
			return nil, 0, fmt.Errorf("failed to marshal request body: %w", err)
		}
		reqBody = bytes.NewBuffer(jsonBody)
	}

	req, err := http.NewRequest(method, url, reqBody)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	for _, opt := range opts {
		opt(req)
	}

	if c.verbose {
		fmt.Printf("[%s] %s\n", method, url)
	}

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, 0, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, resp.StatusCode, fmt.Errorf("failed to read response body: %w", err)
	}

	var apiResp APIResponse
	if err := json.Unmarshal(respBody, &apiResp); err != nil {
		return nil, resp.StatusCode, fmt.Errorf("status %d: %s", resp.StatusCode, string(respBody))
	}

	if c.verbose && !apiResp.Success {
		fmt.Printf("  Response: %d - %s\n", resp.StatusCode, apiResp.Message)
	}

	return &apiResp, resp.StatusCode, nil
}

func (c *Client) Get(path string, opts ...RequestOption) (*APIResponse, int, error) {
	return c.doRequest(http.MethodGet, path, nil, opts...)
}

func (c *Client) Post(path string, body interface{}, opts ...RequestOption) (*APIResponse, int, error) {
	return c.doRequest(http.MethodPost, path, body, opts...)
}

func (c *Client) Put(path string, body interface{}, opts ...RequestOption) (*APIResponse, int, error) {
	return c.doRequest(http.MethodPut, path, body, opts...)
}

func (c *Client) Delete(path string, opts ...RequestOption) (*APIResponse, int, error) {
	return c.doRequest(http.MethodDelete, path, nil, opts...)
}

func (c *Client) HealthCheck() error {
	resp, err := c.httpClient.Get(c.baseURL + "/health")
	if err != nil {
		return fmt.Errorf("health check failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("health check returned status %d", resp.StatusCode)
	}

	return nil
}
