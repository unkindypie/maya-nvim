package buffer

// Batch represents deferred editor operations
type Batch interface {
	Execute() error
}

// SyncResult contains state after syncing with editor
type SyncResult struct {
	BufferChanged bool
	OldPath       string
	NewPath       string
}
