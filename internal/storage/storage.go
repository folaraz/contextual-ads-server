package storage

import (
	"context"
	"encoding/binary"
	"encoding/json"
	"log"
	"math"

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

	return pageContext
}

func QueryAds(pageContext models.PageContext) []models.Ad {
	if len(pageContext.Embedding) == 0 {
		log.Printf("empty embedding; skipping KNN search")
		return nil
	}

	client := GetRedisClient()
	ctx := context.Background()
	buffer := floatsToBytes(pageContext.Embedding)

	results, err := client.FTSearchWithArgs(
		ctx,
		"idx:ads",
		"*=>[KNN 3 @embedding $query_vector AS vector_score]",
		&redis.FTSearchOptions{
			DialectVersion: 2,
			Params: map[string]any{
				"query_vector": buffer,
			},
			// Smaller distance is better.
			SortBy: []redis.FTSearchSortBy{
				{FieldName: "vector_score", Desc: false},
			},
			//Return: []redis.FTSearchReturn{
			//	{FieldName: "vector_score"},
			//	{FieldName: "advertiser"},
			//},
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

	var ads []models.Ad
	for _, doc := range results.Docs {
		raw, ok := doc.Fields["$"]
		if !ok {
			log.Printf("missing $ JSON for id=%s", doc.ID)
			continue
		}
		var a models.Ad
		if err := json.Unmarshal([]byte(raw), &a); err != nil {
			log.Printf("failed to unmarshal doc id=%s: %v", doc.ID, err)
			continue
		}
		ads = append(ads, a)
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
