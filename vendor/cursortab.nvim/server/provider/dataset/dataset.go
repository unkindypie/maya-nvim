// Package dataset implements a metrics sender for the community data collection API.
package dataset

import (
	"context"
	"time"

	"cursortab/client/dataset"
	"cursortab/logger"
	"cursortab/metrics"
)

type Sender struct {
	client   *dataset.Client
	deviceID string
}

func NewSender(deviceID, version, baseURL string) *Sender {
	return &Sender{
		client:   dataset.New(baseURL, version),
		deviceID: deviceID,
	}
}

func (s *Sender) SendMetric(ctx context.Context, event metrics.Event) {
	// Only send outcome events, not "shown"
	if event.Type == metrics.EventShown || event.Snapshot == nil {
		return
	}

	var displayDurationMs int64
	if !event.Info.ShownAt.IsZero() {
		displayDurationMs = time.Since(event.Info.ShownAt).Milliseconds()
	}

	req := &dataset.EventRequest{
		DeviceID:          s.deviceID,
		Outcome:           string(event.Type),
		DisplayDurationMs: displayDurationMs,
		Snapshot:          *event.Snapshot,
	}

	if err := s.client.SendEvent(ctx, req); err != nil {
		logger.Debug("dataset: failed to send %s event: %v", event.Type, err)
	}
}
