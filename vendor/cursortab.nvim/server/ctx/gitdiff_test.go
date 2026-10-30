package ctx

import (
	"strings"
	"testing"

	"cursortab/assert"
)

func TestExtractChangedSymbols_AddedDeclarations(t *testing.T) {
	diff := `diff --git a/server.go b/server.go
--- a/server.go
+++ b/server.go
@@ -5,0 +6,3 @@
+func newHelper(ctx context.Context) error {
+	return nil
+}
@@ -20,0 +24,2 @@
+type Config struct {
+	Port int
`

	symbols := extractChangedSymbols(diff, 50)

	found := map[string]bool{}
	for _, s := range symbols {
		found[s] = true
	}
	assert.True(t, found["+func newHelper(ctx context.Context) error {"], "should find added func")
	assert.True(t, found["+type Config struct {"], "should find added type")
}

func TestExtractChangedSymbols_RemovedDeclarations(t *testing.T) {
	diff := `diff --git a/server.go b/server.go
--- a/server.go
+++ b/server.go
@@ -5,3 +5,0 @@
-func oldHelper() error {
-	return nil
-}
`

	symbols := extractChangedSymbols(diff, 50)

	found := map[string]bool{}
	for _, s := range symbols {
		found[s] = true
	}
	assert.True(t, found["-func oldHelper() error {"], "should find removed func")
}

func TestExtractChangedSymbols_AddedAndRemoved(t *testing.T) {
	diff := `diff --git a/server.go b/server.go
--- a/server.go
+++ b/server.go
@@ -5,1 +5,1 @@
-func oldName() error {
+func newName() error {
`

	symbols := extractChangedSymbols(diff, 50)

	found := map[string]bool{}
	for _, s := range symbols {
		found[s] = true
	}
	assert.True(t, found["-func oldName() error {"], "should find removed func")
	assert.True(t, found["+func newName() error {"], "should find added func")
}

func TestExtractChangedSymbols_MultipleLanguages(t *testing.T) {
	diff := `diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,0 +2,2 @@
+def handle_request(request):
+    pass
+class UserService:
diff --git a/lib.rs b/lib.rs
--- a/lib.rs
+++ b/lib.rs
@@ -1,0 +2,1 @@
+fn process(data: &[u8]) -> Result<(), Error> {
+impl Handler for Server {
`

	symbols := extractChangedSymbols(diff, 50)

	found := map[string]bool{}
	for _, s := range symbols {
		found[s] = true
	}
	assert.True(t, found["+def handle_request(request):"], "should find Python def")
	assert.True(t, found["+class UserService:"], "should find Python class")
	assert.True(t, found["+fn process(data: &[u8]) -> Result<(), Error> {"], "should find Rust fn")
	assert.True(t, found["+impl Handler for Server {"], "should find Rust impl")
}

func TestExtractChangedSymbols_Empty(t *testing.T) {
	symbols := extractChangedSymbols("", 50)
	assert.Nil(t, symbols, "empty diff")
}

func TestExtractChangedSymbols_NoDeclarations(t *testing.T) {
	diff := `diff --git a/data.txt b/data.txt
--- a/data.txt
+++ b/data.txt
@@ -1,1 +1,1 @@
-old text
+new text
`

	symbols := extractChangedSymbols(diff, 50)
	assert.Equal(t, 0, len(symbols), "no declarations in plain text diff")
}

func TestExtractChangedSymbols_Deduplication(t *testing.T) {
	diff := `diff --git a/main.go b/main.go
--- a/main.go
+++ b/main.go
@@ -5,0 +6,1 @@
+func repeated() {
@@ -20,0 +22,1 @@
+func repeated() {
`

	symbols := extractChangedSymbols(diff, 50)

	count := 0
	for _, s := range symbols {
		if s == "+func repeated() {" {
			count++
		}
	}
	assert.Equal(t, 1, count, "should deduplicate symbols")
}

func TestExtractChangedSymbols_MaxCap(t *testing.T) {
	var sb strings.Builder
	sb.WriteString("diff --git a/big.go b/big.go\n--- a/big.go\n+++ b/big.go\n")
	for i := range 60 {
		sb.WriteString("@@ -1,0 +1,1 @@\n")
		sb.WriteString("+func fn")
		sb.WriteRune(rune('A' + i%26))
		sb.WriteRune(rune('0' + i/26))
		sb.WriteString("() {\n")
	}
	diff := sb.String()

	symbols := extractChangedSymbols(diff, 50)
	assert.LessOrEqual(t, len(symbols), 50, "should cap at maxSymbols")
}

func TestIsDeclarationLine(t *testing.T) {
	cases := []struct {
		line string
		want bool
	}{
		{"func main() {", true},
		{"func(x int) int {", true},
		{"def process(data):", true},
		{"class MyClass:", true},
		{"type Config struct {", true},
		{"struct Node {", true},
		{"fn handle(&self) -> Result<()> {", true},
		{"impl Server {", true},
		{"trait Handler {", true},
		{"enum Color {", true},
		{"interface Reader {", true},
		{"export function create() {", true},
		{"export default function App() {", true},
		{"export const handler =", true},
		{"export class Service {", true},
		{"async function fetch() {", true},
		{"public void run() {", true},
		{"private int count;", true},
		{"protected String name;", true},
		{"static void helper() {", true},
		// Non-declarations
		{"const port = 8080", false},
		{"    return nil", false},
		{"x := 42", false},
		{"// func commented() {", false},
		{"", false},
		{"  func indented() {", false},
	}

	for _, tc := range cases {
		result := isDeclarationLine(tc.line)
		if result != tc.want {
			t.Errorf("isDeclarationLine(%q) = %v, want %v", tc.line, result, tc.want)
		}
	}
}
