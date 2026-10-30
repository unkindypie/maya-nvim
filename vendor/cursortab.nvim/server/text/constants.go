package text

const (
	// SimilarityThreshold is the minimum similarity score for considering
	// two lines as corresponding (modification vs addition/deletion).
	// Below this threshold, lines are treated as unrelated.
	SimilarityThreshold = 0.3

	// MaxReplaceCharsSpan is the maximum character count of the changed span
	// (whichever side is larger) for a modification to use replace_chars
	// rendering. Beyond this, the change is shown as a full-line modification.
	MaxReplaceCharsSpan = 12
)
