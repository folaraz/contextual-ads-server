package storage

import (
	"context"
	"encoding/binary"
	"encoding/json"
	"log"
	"math"
	"sort"
	"strconv"
	"sync"

	"github.com/folaraz/contextual-ads-server/internal/models"
	"github.com/redis/go-redis/v9"
)

type AdTaxonomyMapping struct {
	ContentToProduct map[string]string
	ProductToContent map[string]string
}

var (
	adTaxonomyMapping AdTaxonomyMapping
	adContentMu       sync.RWMutex
	adContentOnce     sync.Once
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
	keywordMap := pageContext.Keywords

	keywords := make([]string, 0, len(keywordMap))
	for k := range keywordMap {
		keywords = append(keywords, "kw:"+k)
	}

	if len(chunkContexts) == 0 {
		log.Printf("no chunk embeddings; skipping KNN search")
		return nil
	}

	client := GetRedisClient()
	ctx := context.Background()

	var ads = make(map[string]models.AdRankResult)

	for _, chunkContext := range chunkContexts {
		buffer := floatsToBytes(chunkContext.Embedding)
		getAdsFromRediSearch(ctx, client, buffer, ads)
	}
	//
	//buffer := floatsToBytes(pageContext.Embedding)
	//getAdsFromRediSearch(ctx, client, buffer, ads)

	adResults := make([]models.AdRankResult, 0, len(ads))
	for _, ad := range ads {
		adResults = append(adResults, ad)
	}

	sort.Slice(adResults, func(i, j int) bool {
		return adResults[i].VectorScore > adResults[j].VectorScore
	})

	return adResults
}

func getAdsFromRediSearch(ctx context.Context, client *redis.Client, buffer []byte, ads map[string]models.AdRankResult) {
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
				{FieldName: "vector_score", Desc: true},
			},
		},
	).Result()

	if err != nil {
		log.Printf("failed to query RediSearch: %v", err)
		return
	}

	if results.Total == 0 || len(results.Docs) == 0 {
		log.Printf("no results from RediSearch (total=%d)", results.Total)
		return
	}

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
		vectorScore, e := strconv.ParseFloat(vectorScoreStr, 64)
		if e != nil {
			log.Printf("failed to parse vector score for id=%s: %v", doc.ID, e)
			continue
		}
		//if vectorScore < 0.65 {
		//	log.Printf("skipping ad id=%s with vector score %.4f", doc.ID, vectorScore)
		//	continue
		//}

		adInCache, ok := ads[a.ID]
		if !ok {
			adRank := models.AdRankResult{
				Ad:          a,
				VectorScore: vectorScore,
			}
			ads[a.ID] = adRank
		} else {
			if adInCache.VectorScore < vectorScore {
				adInCache.VectorScore = vectorScore
				ads[a.ID] = adInCache
			}
		}

	}
}

func floatsToBytes(fs []float32) []byte {
	buf := make([]byte, len(fs)*4)

	for i, f := range fs {
		u := math.Float32bits(f)
		binary.NativeEndian.PutUint32(buf[i*4:], u)
	}

	return buf
}

func GetAdMapping() AdTaxonomyMapping {
	adContentOnce.Do(func() {
		if err := LoadAdContentToProductMapping(); err != nil {
			log.Printf("failed to load ad content to product mapping: %v", err)
			adTaxonomyMapping = AdTaxonomyMapping{
				ContentToProduct: make(map[string]string),
				ProductToContent: make(map[string]string),
			}
		}
	})

	adContentMu.RLock()
	defer adContentMu.RUnlock()

	// doing this will prevent external modification of the cache
	return AdTaxonomyMapping{
		ContentToProduct: adTaxonomyMapping.ContentToProduct,
		ProductToContent: adTaxonomyMapping.ProductToContent,
	}
}

func LoadAdContentToProductMapping() error {
	ctx := context.Background()
	client := GetRedisClient()

	c_t_p, err1 := client.HGetAll(ctx, "iab_content_to_product").Result()
	p_t_c, err2 := client.HGetAll(ctx, "iab_product_to_content").Result()

	if err1 != nil {
		panic(err1)
	}
	if err2 != nil {
		panic(err2)
	}

	adContentToProduct := make(map[string]string)
	adProductToContent := make(map[string]string)

	for adContentID, productsStr := range c_t_p {
		var product string
		json.Unmarshal([]byte(productsStr), &product)
		adContentToProduct[adContentID] = product
	}

	for adProductID, contentsStr := range p_t_c {
		var content string
		json.Unmarshal([]byte(contentsStr), &content)
		adProductToContent[adProductID] = content
	}

	adContentMu.Lock()
	adTaxonomyMapping = AdTaxonomyMapping{
		ContentToProduct: adContentToProduct,
		ProductToContent: adProductToContent,
	}
	adContentMu.Unlock()

	return nil

}
