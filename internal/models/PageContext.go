package models

type PageContext struct {
	Keywords      []string          `redis:"keywords"`
	Entities      []string          `redis:"entities"`
	Topics        []string          `redis:"topics"`
	Embedding     []float32         `redis:"embedding"`
	Metadata      map[string]string `redis:"meta_data" json:"meta_data"`
	ChunkContexts []ChunkContext    `redis:"chunk_context,json" json:"chunk_context"`
}

type ChunkContext struct {
	Embedding []float32 `redis:"embedding" json:"embedding"`
	ChunkText string    `redis:"chunk_text" json:"chunk_text"`
}
