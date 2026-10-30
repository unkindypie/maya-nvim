// Package dataset provides an HTTP client for the community data collection API.
package dataset

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"cursortab/metrics"
)

const DefaultURL = "https://api.cursortab.com"

// EventRequest is the payload sent to POST /events.
type EventRequest struct {
	DeviceID          string `json:"device_id"`
	Outcome           string `json:"outcome"`
	DisplayDurationMs int64  `json:"display_duration_ms"`
	metrics.Snapshot
}

// Client sends anonymous completion metrics to the community API.
type Client struct {
	baseURL    string
	version    string
	httpClient *http.Client
}

func New(baseURL, version string) *Client {
	if baseURL == "" {
		baseURL = DefaultURL
	}
	return &Client{
		baseURL: baseURL,
		version: version,
		httpClient: &http.Client{
			Timeout: 5 * time.Second,
		},
	}
}

func (c *Client) SendEvent(ctx context.Context, req *EventRequest) error {
	body, err := json.Marshal(req)
	if err != nil {
		return fmt.Errorf("marshal: %w", err)
	}

	httpReq, err := http.NewRequestWithContext(ctx, "POST", c.baseURL+"/events", bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("create request: %w", err)
	}

	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("X-Plugin-Version", c.version)

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return fmt.Errorf("send: %w", err)
	}
	defer resp.Body.Close()
	io.Copy(io.Discard, resp.Body)

	if resp.StatusCode != http.StatusCreated {
		return fmt.Errorf("unexpected status %d", resp.StatusCode)
	}

	return nil
}
