package metrics

import (
	"testing"

	"cursortab/assert"
)

func TestEventTypes(t *testing.T) {
	// Verify event type constants
	assert.Equal(t, EventType("shown"), EventShown, "EventShown")
	assert.Equal(t, EventType("accepted"), EventAccepted, "EventAccepted")
	assert.Equal(t, EventType("rejected"), EventRejected, "EventRejected")
	assert.Equal(t, EventType("ignored"), EventIgnored, "EventIgnored")
}

func TestCompletionInfo(t *testing.T) {
	info := CompletionInfo{
		ID:        "test-id",
		Additions: 5,
		Deletions: 3,
	}

	assert.Equal(t, "test-id", info.ID, "ID")
	assert.Equal(t, 5, info.Additions, "Additions")
	assert.Equal(t, 3, info.Deletions, "Deletions")
}

func TestEvent(t *testing.T) {
	event := Event{
		Type: EventAccepted,
		Info: CompletionInfo{
			ID:        "event-id",
			Additions: 2,
			Deletions: 1,
		},
	}

	assert.Equal(t, EventAccepted, event.Type, "Type")
	assert.Equal(t, "event-id", event.Info.ID, "Info.ID")
}
