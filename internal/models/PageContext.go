package models

type Entity struct {
	Text string `json:"text" redis:"text"`
	Type string `json:"type" redis:"type"` // ORG, PRODUCT, PERSON, EVENT, GPE
}

type Topic struct {
	IabID          string  `json:"iab_id" redis:"iab_id"`
	Name           string  `json:"name" redis:"name"`
	Tier           int     `json:"tier" redis:"tier"`
	RelevanceScore float64 `json:"score" redis:"score"`
}

type PageMetadata struct {
	URL         string `json:"url" redis:"url"`
	Title       string `json:"title" redis:"title"`
	Description string `json:"description" redis:"description"`
}

type ChunkContext struct {
	Content   string    `json:"content" redis:"content"`
	Embedding []float32 `json:"embedding" redis:"embedding"`
}

type PageContext struct {
	PageURLHash   string             `json:"page_url_hash" redis:"page_url_hash"`
	Keywords      map[string]float64 `json:"keywords" redis:"keywords"` // keyword -> relevance score
	Entities      []Entity           `json:"entities" redis:"entities"` // list of named entities
	Topics        map[string]Topic   `json:"topics" redis:"topics"`     // iab_id -> Topic
	PageEmbedding []float32          `json:"page_embedding" redis:"page_embedding"`
	Metadata      PageMetadata       `json:"meta_data" redis:"meta_data"`
	ChunkContext  []ChunkContext     `json:"chunk_context" redis:"chunk_context"`
	ProcessedAt   string             `json:"processed_at" redis:"processed_at"`
}
