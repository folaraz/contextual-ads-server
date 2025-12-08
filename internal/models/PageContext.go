package models

type PageContext struct {
	Keywords      map[string]float64 `redis:"keywords"`
	Entities      map[string]string  `redis:"entities"`
	Topics        map[string]Topic   `redis:"topics"`
	Embedding     []float32          `redis:"embedding"`
	Metadata      map[string]string  `redis:"meta_data" json:"meta_data"`
	ChunkContexts []ChunkContext     `redis:"chunk_context,json" json:"chunk_context"`
}

type ChunkContext struct {
	Embedding []float32 `redis:"embedding" json:"embedding"`
	ChunkText string    `redis:"content" json:"content"`
}
