package ads

import (
	"context"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"math"
	"sort"
	"strconv"
	"time"

	"github.com/folaraz/contextual-ads-server/internal/models"
	"github.com/folaraz/contextual-ads-server/internal/observability"
	"github.com/folaraz/contextual-ads-server/internal/storage/redis"
	goredis "github.com/redis/go-redis/v9"
)

const (
	minCosineSimilarityThreshold = 0.2
	redisAdIndex                 = "idx:ads"
	defaultKnnCount              = 50
	maxChunksForSearch           = 3
)

type AdRankingService struct {
	redisClient *goredis.Client
}

func NewAdRankingService() *AdRankingService {
	return &AdRankingService{
		redisClient: redis.GetRedisClient(),
	}
}

func (s *AdRankingService) RankAds(ctx context.Context, pageContext models.PageContext,
	ads map[uint32]*models.Ad) []models.AdVectorResult {
	start := time.Now()

	if len(pageContext.ChunkContext) == 0 && len(pageContext.PageEmbedding) == 0 {
		observability.Debug(ctx, "No embeddings available, skipping vector search")
		return nil
	}

	if ads == nil || len(ads) == 0 {
		observability.Debug(ctx, "No ads available, skipping vector search")
		return nil
	}

	// Dynamically set KNN count: no need to search more than the candidate set
	knnCount := defaultKnnCount
	if len(ads) < knnCount {
		knnCount = len(ads)
	}

	// Collect all embeddings to search (capped chunks + page embedding)
	embeddings := s.collectEmbeddings(pageContext)
	if len(embeddings) == 0 {
		observability.Warn(ctx, "No valid embeddings to search")
		return nil
	}

	// Pipeline all KNN queries into a single Redis round-trip
	adScores := s.pipelinedVectorSearch(ctx, embeddings, knnCount, ads)

	results := s.sortByScore(adScores)

	observability.Debug(ctx, "Ad ranking complete",
		"results", len(results),
		"candidates", len(ads),
		"embeddings_searched", len(embeddings),
		"chunks_total", len(pageContext.ChunkContext),
		"chunks_capped", maxChunksForSearch,
		"knn_count", knnCount,
		"duration_ms", time.Since(start).Milliseconds())

	return results
}

// collectEmbeddings gathers chunk embeddings (capped) and the page-level embedding.
func (s *AdRankingService) collectEmbeddings(pageContext models.PageContext) [][]float32 {
	embeddings := make([][]float32, 0, maxChunksForSearch+1)

	// Add chunk embeddings, capped at maxChunksForSearch
	chunksAdded := 0
	for _, chunk := range pageContext.ChunkContext {
		if chunksAdded >= maxChunksForSearch {
			break
		}
		if len(chunk.Embedding) > 0 {
			embeddings = append(embeddings, chunk.Embedding)
			chunksAdded++
		}
	}

	// Add page-level embedding
	if len(pageContext.PageEmbedding) > 0 {
		embeddings = append(embeddings, pageContext.PageEmbedding)
	}

	return embeddings
}

func (s *AdRankingService) pipelinedVectorSearch(ctx context.Context, embeddings [][]float32, knnCount int,
	ads map[uint32]*models.Ad) map[uint32]*models.AdVectorResult {
	adScores := make(map[uint32]*models.AdVectorResult)

	if s.redisClient == nil {
		return adScores
	}

	pipe := s.redisClient.Pipeline()
	cmds := make([]*goredis.FTSearchCmd, 0, len(embeddings))

	query := fmt.Sprintf("*=>[KNN %d @embedding $query_vector AS cosine_distance]", knnCount)

	for _, embedding := range embeddings {
		queryVector := floatsToBytes(embedding)
		cmd := pipe.FTSearchWithArgs(
			ctx,
			redisAdIndex,
			query,
			&goredis.FTSearchOptions{
				DialectVersion: 2,
				Params: map[string]any{
					"query_vector": queryVector,
				},
			},
		)
		cmds = append(cmds, cmd)
	}

	pipeStart := time.Now()
	_, err := pipe.Exec(ctx)
	pipeDuration := time.Since(pipeStart)

	if err != nil {
		observability.Warn(ctx, "Pipelined vector search exec failed", "error", err,
			"duration_ms", pipeDuration.Milliseconds())
	}

	observability.Info(ctx, "Pipelined vector search complete",
		"queries", len(cmds),
		"duration_ms", pipeDuration.Milliseconds())

	// Collect results from all pipeline commands
	for _, cmd := range cmds {
		results, err := cmd.Result()
		if err != nil {
			observability.Warn(ctx, "Individual vector search in pipeline failed", "error", err)
			continue
		}

		if results.Total == 0 {
			continue
		}

		s.collectSearchResults(results, ads, adScores)
	}

	return adScores
}

// collectSearchResults processes FT.SEARCH results and updates adScores.
func (s *AdRankingService) collectSearchResults(results goredis.FTSearchResult,
	ads map[uint32]*models.Ad, adScores map[uint32]*models.AdVectorResult) {
	for _, doc := range results.Docs {
		rawJSON, ok := doc.Fields["$"]
		if !ok {
			continue
		}

		var vectorDoc struct {
			AdID int32 `json:"ad_id"`
		}
		if err := json.Unmarshal([]byte(rawJSON), &vectorDoc); err != nil {
			continue
		}

		distanceStr, ok := doc.Fields["cosine_distance"]
		if !ok {
			continue
		}

		cosineDistance, err := strconv.ParseFloat(distanceStr, 64)
		if err != nil {
			continue
		}

		cosineSimilarity := 1.0 - cosineDistance

		if cosineSimilarity < minCosineSimilarityThreshold {
			continue
		}

		adID := uint32(vectorDoc.AdID)

		ad, exists := ads[adID]
		if !exists {
			continue
		}

		if existing, exists := adScores[adID]; exists {
			if cosineSimilarity > existing.VectorScore {
				existing.VectorScore = cosineSimilarity
			}
		} else {
			adScores[adID] = &models.AdVectorResult{Ad: *ad, VectorScore: cosineSimilarity}
		}
	}
}

func (s *AdRankingService) sortByScore(adScores map[uint32]*models.AdVectorResult) []models.AdVectorResult {
	results := make([]models.AdVectorResult, 0, len(adScores))
	for _, result := range adScores {
		results = append(results, *result)
	}

	sort.Slice(results, func(i, j int) bool {
		return results[i].VectorScore > results[j].VectorScore
	})

	return results
}

func floatsToBytes(fs []float32) []byte {
	buf := make([]byte, len(fs)*4)
	for i, f := range fs {
		binary.NativeEndian.PutUint32(buf[i*4:], math.Float32bits(f))
	}
	return buf
}
