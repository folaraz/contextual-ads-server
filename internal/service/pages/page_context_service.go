package pages

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/folaraz/contextual-ads-server/internal/models"
	"github.com/folaraz/contextual-ads-server/internal/observability"
	"github.com/folaraz/contextual-ads-server/internal/storage/redis"
	goredis "github.com/redis/go-redis/v9"
)

type PageContextService struct {
}

func NewPageContextService() *PageContextService {
	return &PageContextService{}
}

type PageContextResult struct {
	Context  models.PageContext
	CacheHit bool
	URLHash  string
	Error    error
}

func (s *PageContextService) GetPageContext(urlHash string) PageContextResult {
	ctx := context.Background()
	client := redis.GetRedisClient()

	if client == nil {
		return PageContextResult{
			CacheHit: false,
			URLHash:  urlHash,
			Error:    fmt.Errorf("redis client not initialized"),
		}
	}

	start := time.Now()
	pageContext, found, err := s.fetchPageContextHash(ctx, client, urlHash)
	cacheDuration := time.Since(start)

	observability.RecordCacheOperation(ctx, "page_context", "get", found, cacheDuration)

	if err != nil {
		return PageContextResult{
			CacheHit: false,
			URLHash:  urlHash,
			Error:    err,
		}
	}

	if !found {
		return PageContextResult{
			CacheHit: false,
			URLHash:  urlHash,
			Error:    nil,
		}
	}

	pageEmbedding, chunkContexts := s.fetchEmbeddings(ctx, client, urlHash)
	pageContext.PageEmbedding = pageEmbedding
	pageContext.ChunkContext = chunkContexts

	observability.Debug(ctx, "Page context cache hit", "url_hash", urlHash)

	return PageContextResult{
		Context:  pageContext,
		CacheHit: true,
		URLHash:  urlHash,
		Error:    nil,
	}
}

func (s *PageContextService) fetchPageContextHash(ctx context.Context, client *goredis.Client,
	urlHash string) (models.PageContext, bool, error) {
	redisKey := "page:" + urlHash
	result, err := client.HGetAll(ctx, redisKey).Result()

	if err != nil {
		observability.Error(ctx, "Failed to get page context from Redis", "url_hash", urlHash, "error", err)
		return models.PageContext{}, false, fmt.Errorf("redis error: %w", err)
	}

	if len(result) == 0 {
		observability.Debug(ctx, "Page context cache miss", "url_hash", urlHash)
		return models.PageContext{}, false, nil
	}

	pageContext := models.PageContext{
		PageURLHash: urlHash,
	}

	if keywordsStr, ok := result["keywords"]; ok {
		if err := json.Unmarshal([]byte(keywordsStr), &pageContext.Keywords); err != nil {
			observability.Warn(ctx, "Failed to unmarshal keywords", "url_hash", urlHash, "error", err)
		}
	}

	if entitiesStr, ok := result["entities"]; ok {
		if err := json.Unmarshal([]byte(entitiesStr), &pageContext.Entities); err != nil {
			observability.Warn(ctx, "Failed to unmarshal entities", "url_hash", urlHash, "error", err)
		}
	}

	if topicsStr, ok := result["topics"]; ok {
		if err := json.Unmarshal([]byte(topicsStr), &pageContext.Topics); err != nil {
			observability.Warn(ctx, "Failed to unmarshal topics", "url_hash", urlHash, "error", err)
		}
	}

	if metaDataStr, ok := result["meta_data"]; ok {
		if err := json.Unmarshal([]byte(metaDataStr), &pageContext.Metadata); err != nil {
			observability.Warn(ctx, "Failed to unmarshal metadata", "url_hash", urlHash, "error", err)
		}
	}

	if processedAt, ok := result["processed_at"]; ok {
		pageContext.ProcessedAt = processedAt
	}

	return pageContext, true, nil
}

func (s *PageContextService) fetchEmbeddings(ctx context.Context, client *goredis.Client, urlHash string) ([]float32,
	[]models.ChunkContext) {
	var pageEmbedding []float32
	var chunkContexts []models.ChunkContext

	embeddingKey := "page:embedding:" + urlHash
	chunkKey := "page:chunks:" + urlHash

	// Pipeline both GET calls into a single Redis round-trip
	pipeStart := time.Now()
	pipe := client.Pipeline()
	embCmd := pipe.Get(ctx, embeddingKey)
	chunkCmd := pipe.Get(ctx, chunkKey)
	_, _ = pipe.Exec(ctx)
	pipeDuration := time.Since(pipeStart)

	// Process embedding result
	embeddingData, err := embCmd.Bytes()
	if err != nil {
		observability.RecordCacheOperation(ctx, "page_embedding", "get", false, pipeDuration)
		if err != goredis.Nil {
			observability.Warn(ctx, "Failed to get page embedding", "url_hash", urlHash, "error", err)
		}
	} else {
		observability.RecordCacheOperation(ctx, "page_embedding", "get", true, pipeDuration)
		var embedding []float64
		if err := json.Unmarshal(embeddingData, &embedding); err != nil {
			observability.Warn(ctx, "Failed to unmarshal page embedding", "url_hash", urlHash, "error", err)
		} else {
			pageEmbedding = make([]float32, len(embedding))
			for i, v := range embedding {
				pageEmbedding[i] = float32(v)
			}
		}
	}

	// Process chunk result
	chunkData, err := chunkCmd.Bytes()
	if err != nil {
		observability.RecordCacheOperation(ctx, "page_chunks", "get", false, pipeDuration)
		if err != goredis.Nil {
			observability.Warn(ctx, "Failed to get chunk data", "url_hash", urlHash, "error", err)
		}
	} else {
		observability.RecordCacheOperation(ctx, "page_chunks", "get", true, pipeDuration)
		chunkContexts = parseChunkContexts(chunkData, urlHash)
	}

	return pageEmbedding, chunkContexts
}

func parseChunkContexts(data []byte, urlHash string) []models.ChunkContext {
	var rawChunks []struct {
		Content    string    `json:"content"`
		Embedding  []float64 `json:"embedding"`
		ChunkIndex int       `json:"chunk_index"`
	}

	if err := json.Unmarshal(data, &rawChunks); err != nil {
		observability.Warn(context.Background(), "Failed to unmarshal chunk contexts", "url_hash", urlHash, "error", err)
		return nil
	}

	chunks := make([]models.ChunkContext, 0, len(rawChunks))
	for _, raw := range rawChunks {
		embedding := make([]float32, len(raw.Embedding))
		for i, v := range raw.Embedding {
			embedding[i] = float32(v)
		}

		chunks = append(chunks, models.ChunkContext{
			Content:   raw.Content,
			Embedding: embedding,
		})
	}

	return chunks
}

func (s *PageContextService) GetPageContextOrDefault(urlHash string, defaultKeywords []string) PageContextResult {
	result := s.GetPageContext(urlHash)

	if !result.CacheHit {
		observability.Debug(context.Background(), "Using default page context", "url_hash", urlHash)
		keywords := make(map[string]float64)
		for _, kw := range defaultKeywords {
			keywords[kw] = 1.0
		}
		return PageContextResult{
			Context: models.PageContext{
				Keywords: keywords,
			},
			CacheHit: false,
			URLHash:  urlHash,
			Error:    result.Error,
		}
	}

	return result
}
