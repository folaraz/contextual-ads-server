package storage

import (
	"context"
	"encoding/binary"
	"encoding/json"
	"log"
	"math"
	"strconv"

	"github.com/folaraz/contextual-ads-server/internal/models"
	"github.com/redis/go-redis/v9"
)

func GetContext(urlHash string) models.PageContext {
	ctx := context.Background()
	client := GetRedisClient()

	result, err := client.HGetAll(ctx, "page:"+urlHash).Result()

	if err != nil {
		panic(err)
	}

	var pageContext models.PageContext

	if keywordsStr, ok := result["keywords"]; ok {
		json.Unmarshal([]byte(keywordsStr), &pageContext.Keywords)
	}

	if entitiesStr, ok := result["entities"]; ok {
		json.Unmarshal([]byte(entitiesStr), &pageContext.Entities)
	}

	if embeddingStr, ok := result["embedding"]; ok {
		json.Unmarshal([]byte(embeddingStr), &pageContext.Embedding)
	}

	if topicsStr, ok := result["topics"]; ok {
		json.Unmarshal([]byte(topicsStr), &pageContext.Topics)
	}

	if metaDataStr, ok := result["meta_data"]; ok {
		json.Unmarshal([]byte(metaDataStr), &pageContext.Metadata)
	}

	if chunkContextsStr, ok := result["chunk_context"]; ok {
		json.Unmarshal([]byte(chunkContextsStr), &pageContext.ChunkContexts)
	}

	return pageContext
}

func QueryAds(pageContext models.PageContext) []models.AdRankResult {
	chunkContexts := pageContext.ChunkContexts

	if len(chunkContexts) == 0 {
		log.Printf("no chunk embeddings; skipping KNN search")
		return nil
	}

	client := GetRedisClient()
	ctx := context.Background()

	var ads []models.AdRankResult

	for _, chunkContext := range chunkContexts {
		buffer := floatsToBytes(chunkContext.Embedding)
		ads = append(ads, getAdsFromRediSearch(ctx, client, buffer)...)
	}
	return ads
}

func getAdsFromRediSearch(ctx context.Context, client *redis.Client, buffer []byte) []models.AdRankResult {
	results, err := client.FTSearchWithArgs(
		ctx,
		"idx:ads",
		"*=>[KNN 10 @embedding $query_vector AS vector_score]",
		&redis.FTSearchOptions{
			DialectVersion: 2,
			Params: map[string]any{
				"query_vector": buffer,
			},
			SortBy: []redis.FTSearchSortBy{
				{FieldName: "vector_score", Desc: false},
			},
		},
	).Result()

	if err != nil {
		log.Printf("failed to query RediSearch: %v", err)
		return nil
	}

	if results.Total == 0 || len(results.Docs) == 0 {
		log.Printf("no results from RediSearch (total=%d)", results.Total)
		return nil
	}

	var ads []models.AdRankResult
	var seenAdIDs = make(map[string]bool)
	for _, doc := range results.Docs {
		raw, ok := doc.Fields["$"]
		vectorScoreStr, ok := doc.Fields["vector_score"]
		if !ok {
			log.Printf("missing $ JSON for id=%s", doc.ID)
			continue
		}
		var a models.Ad
		if err := json.Unmarshal([]byte(raw), &a); err != nil {
			log.Printf("failed to unmarshal doc id=%s: %v", doc.ID, err)
			continue
		}
		if seenAdIDs[doc.ID] {
			continue
		}
		vectorScore, e := strconv.ParseFloat(vectorScoreStr, 64)
		if e != nil {
			log.Printf("failed to parse vector score for id=%s: %v", doc.ID, e)
			continue
		}
		if vectorScore > 0.65 {
			log.Printf("skipping ad id=%s with vector score %.4f", doc.ID, vectorScore)
			continue
		}
		adRank := models.AdRankResult{
			Ad:          a,
			VectorScore: vectorScore,
		}
		ads = append(ads, adRank)
	}
	return ads
}

func floatsToBytes(fs []float32) []byte {
	buf := make([]byte, len(fs)*4)

	for i, f := range fs {
		u := math.Float32bits(f)
		binary.NativeEndian.PutUint32(buf[i*4:], u)
	}

	return buf
}
