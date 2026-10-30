package main

import (
	"crypto/rand"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"cursortab/logger"
)

// loadOrCreateDeviceID reads a persistent device ID from stateDir/device_id,
// or generates and stores a new UUID if the file doesn't exist.
func loadOrCreateDeviceID(stateDir string) string {
	if stateDir == "" {
		return newUUID4()
	}

	path := filepath.Join(stateDir, "device_id")

	data, err := os.ReadFile(path)
	if err == nil {
		id := strings.TrimSpace(string(data))
		if id != "" {
			return id
		}
	}

	id := newUUID4()
	if err := os.WriteFile(path, []byte(id), 0644); err != nil {
		logger.Warn("failed to write device_id: %v", err)
	}
	return id
}

// newUUID4 generates an RFC 4122 version 4 UUID from 128 bits of
// cryptographically secure random data.
func newUUID4() string {
	var b [16]byte
	_, _ = rand.Read(b[:])
	// Set version field (bits 4-7 of byte 6) to 0100 (version 4).
	b[6] = (b[6] & 0x0f) | 0x40
	// Set variant field (bits 6-7 of byte 8) to 10 (RFC 4122).
	b[8] = (b[8] & 0x3f) | 0x80
	return fmt.Sprintf("%08x-%04x-%04x-%04x-%012x",
		b[0:4], b[4:6], b[6:8], b[8:10], b[10:16])
}
