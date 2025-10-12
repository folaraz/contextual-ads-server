package models

type PageContext struct {
	Keywords  []string          `redis:"keywords"`
	Entities  []string          `redis:"entities"`
	Topics    []string          `redis:"topics"`
	Embedding []float32         `redis:"embedding"`
	Metadata  map[string]string `redis:"metadata"`
}
