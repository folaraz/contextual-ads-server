package cache

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"sync"

	db "github.com/folaraz/contextual-ads-server/db/sqlc"
)

type IABTopicInfo struct {
	ID       int32  `json:"id"`
	Name     string `json:"name"`
	ParentID *int32 `json:"parent_id,omitempty"`
	Tier     int32  `json:"tier"`
	Type     string `json:"type"`
}

type TaxonomyMapping struct {
	ContentToProduct map[string]string // content topic ID -> product topic ID
	ProductToContent map[string]string // product topic ID -> content topic ID
}

type TaxonomyCache struct {
	mapping   TaxonomyMapping
	iabTopics map[int32]IABTopicInfo // topic ID -> topic info
	mu        sync.RWMutex
	db        *sql.DB
	initOnce  sync.Once
	initErr   error
}

var (
	globalTaxonomyCache *TaxonomyCache
	cacheOnce           sync.Once
)

func InitTaxonomyCache(database *sql.DB) error {
	var err error
	cacheOnce.Do(func() {
		globalTaxonomyCache = &TaxonomyCache{
			db:        database,
			iabTopics: make(map[int32]IABTopicInfo),
			mapping: TaxonomyMapping{
				ContentToProduct: make(map[string]string),
				ProductToContent: make(map[string]string),
			},
		}
		err = globalTaxonomyCache.loadAll()
	})
	return err
}

func NewTaxonomyCacheFromData(mapping TaxonomyMapping) *TaxonomyCache {
	return &TaxonomyCache{
		mapping:   mapping,
		iabTopics: make(map[int32]IABTopicInfo),
	}
}

func GetTaxonomyCache() *TaxonomyCache {
	if globalTaxonomyCache == nil {
		log.Println("Warning: TaxonomyCache not initialized")
		return &TaxonomyCache{
			iabTopics: make(map[int32]IABTopicInfo),
			mapping: TaxonomyMapping{
				ContentToProduct: make(map[string]string),
				ProductToContent: make(map[string]string),
			},
		}
	}
	return globalTaxonomyCache
}

func (tc *TaxonomyCache) loadAll() error {
	ctx := context.Background()

	if tc.db != nil {
		if err := tc.loadIABTopicsFromDB(ctx); err != nil {
			log.Printf("Warning: Failed to load IAB topics from database: %v", err)
		}
	}

	log.Printf("Taxonomy cache loaded: %d topics, %d content->product mappings, %d product->content mappings", len(tc.iabTopics), len(tc.mapping.ContentToProduct), len(tc.mapping.ProductToContent))

	return nil
}

func (tc *TaxonomyCache) loadIABTopicsFromDB(ctx context.Context) error {
	if tc.db == nil {
		return fmt.Errorf("database connection not available")
	}

	queries := db.New(tc.db)
	topics, err := queries.ListIABTopics(ctx)
	if err != nil {
		return fmt.Errorf("failed to query IAB topics: %w", err)
	}

	tc.mu.Lock()
	defer tc.mu.Unlock()

	for _, topic := range topics {
		var parentID *int32
		if topic.ParentID.Valid {
			parentID = &topic.ParentID.Int32
		}

		topicType := ""
		if topic.Type.Valid {
			topicType = topic.Type.String
		}

		tc.iabTopics[topic.ID] = IABTopicInfo{
			ID:       topic.ID,
			Name:     topic.Name,
			ParentID: parentID,
			Tier:     topic.Tier,
			Type:     topicType,
		}
	}

	return nil
}

func (tc *TaxonomyCache) GetMapping() TaxonomyMapping {
	tc.mu.RLock()
	defer tc.mu.RUnlock()

	return TaxonomyMapping{
		ContentToProduct: tc.copyStringMap(tc.mapping.ContentToProduct),
		ProductToContent: tc.copyStringMap(tc.mapping.ProductToContent),
	}
}

func (tc *TaxonomyCache) GetContentToProductMapping() map[string]string {
	tc.mu.RLock()
	defer tc.mu.RUnlock()
	return tc.copyStringMap(tc.mapping.ContentToProduct)
}

func (tc *TaxonomyCache) GetProductToContentMapping() map[string]string {
	tc.mu.RLock()
	defer tc.mu.RUnlock()
	return tc.copyStringMap(tc.mapping.ProductToContent)
}

func (tc *TaxonomyCache) GetIABTopic(topicID int32) (IABTopicInfo, bool) {
	tc.mu.RLock()
	defer tc.mu.RUnlock()
	topic, exists := tc.iabTopics[topicID]
	return topic, exists
}

func (tc *TaxonomyCache) GetAllIABTopics() map[int32]IABTopicInfo {
	tc.mu.RLock()
	defer tc.mu.RUnlock()

	topics := make(map[int32]IABTopicInfo, len(tc.iabTopics))
	for k, v := range tc.iabTopics {
		topics[k] = v
	}
	return topics
}

func (tc *TaxonomyCache) GetIABTopicsByTier(tier int32) []IABTopicInfo {
	tc.mu.RLock()
	defer tc.mu.RUnlock()

	var topics []IABTopicInfo
	for _, topic := range tc.iabTopics {
		if topic.Tier == tier {
			topics = append(topics, topic)
		}
	}
	return topics
}

func (tc *TaxonomyCache) GetIABTopicsByType(topicType string) []IABTopicInfo {
	tc.mu.RLock()
	defer tc.mu.RUnlock()

	var topics []IABTopicInfo
	for _, topic := range tc.iabTopics {
		if topic.Type == topicType {
			topics = append(topics, topic)
		}
	}
	return topics
}

func (tc *TaxonomyCache) Reload() error {
	return tc.loadAll()
}

func (tc *TaxonomyCache) copyStringMap(m map[string]string) map[string]string {
	result := make(map[string]string, len(m))
	for k, v := range m {
		result[k] = v
	}
	return result
}
