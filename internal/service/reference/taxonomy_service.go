package reference

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log"
	"os"
	"strconv"
	"sync"
	"time"

	db "github.com/folaraz/contextual-ads-server/db/sqlc"
)

type TaxonomyService struct {
	db           *sql.DB
	queries      *db.Queries
	loadedOnce   sync.Once
	loadErr      error
	contentCount int
	productCount int
}

type FlatTaxonomyNode struct {
	ID       string  `json:"id"`
	ParentID *string `json:"parent_id"`
	Name     string  `json:"name"`
	Tier     int     `json:"tier"`
}

func NewTaxonomyService(database *sql.DB) *TaxonomyService {
	return &TaxonomyService{
		db:      database,
		queries: db.New(database),
	}
}

func (s *TaxonomyService) LoadTaxonomies(ctx context.Context) error {
	s.loadedOnce.Do(func() {
		start := time.Now()
		log.Println("Checking IAB Taxonomy data...")

		count, err := s.queries.CountIABTopics(ctx)
		if err != nil {
			s.loadErr = fmt.Errorf("failed to check existing taxonomy data: %w", err)
			return
		}

		if count > 0 {
			log.Printf("IAB Taxonomy already loaded (%d topics). Checking mappings...", count)
			s.contentCount = int(count)

			mappingCount, err := s.queries.CountIABTopicMappings(ctx)
			if err != nil {
				s.loadErr = fmt.Errorf("failed to check existing mapping data: %w", err)
				return
			}

			if mappingCount > 0 {
				log.Printf("IAB Topic Mappings already loaded (%d mappings). Skipping upload.", mappingCount)
				return
			}

			log.Println("Loading IAB Topic Mappings...")
			if err := s.loadMappings(ctx); err != nil {
				s.loadErr = fmt.Errorf("failed to load mappings: %w", err)
				return
			}

			duration := time.Since(start)
			log.Printf("Loaded topic mappings in %v", duration.Round(time.Millisecond))
			return
		}

		log.Println("Loading IAB Taxonomy data...")

		contentCount, err := s.loadFlatTaxonomyFile(ctx, "data/iab_content_taxonomy_flat.json", "CONTENT")
		if err != nil {
			s.loadErr = fmt.Errorf("failed to load content taxonomy: %w", err)
			return
		}
		s.contentCount = contentCount

		productCount, err := s.loadFlatTaxonomyFile(ctx, "data/iab_product_taxonomy_flat.json", "PRODUCT")
		if err != nil {
			s.loadErr = fmt.Errorf("failed to load product taxonomy: %w", err)
			return
		}
		s.productCount = productCount

		log.Println("Loading IAB Topic Mappings...")
		if err := s.loadMappings(ctx); err != nil {
			s.loadErr = fmt.Errorf("failed to load mappings: %w", err)
			return
		}

		duration := time.Since(start)
		log.Printf("Loaded %d content + %d product taxonomy nodes with mappings in %v",
			contentCount, productCount, duration.Round(time.Millisecond))
	})

	return s.loadErr
}

func (s *TaxonomyService) loadFlatTaxonomyFile(ctx context.Context, filePath, taxonomyType string) (int, error) {
	data, err := os.ReadFile(filePath)
	if err != nil {
		return 0, fmt.Errorf("failed to read %s: %w", filePath, err)
	}

	var nodes []FlatTaxonomyNode
	if err := json.Unmarshal(data, &nodes); err != nil {
		return 0, fmt.Errorf("failed to parse %s: %w", filePath, err)
	}

	log.Printf("Loaded %d %s taxonomy nodes from file", len(nodes), taxonomyType)

	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return 0, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback() // Safe to call even after commit - will be a no-op

	txQueries := s.queries.WithTx(tx)

	count := 0
	for _, node := range nodes {
		nodeID, err := strconv.ParseInt(node.ID, 10, 32)
		if err != nil {
			log.Printf("Warning: Invalid node ID %s, skipping: %v", node.ID, err)
			continue
		}

		var parentID sql.NullInt32
		if node.ParentID != nil && *node.ParentID != "" {
			pid, err := strconv.ParseInt(*node.ParentID, 10, 32)
			if err != nil {
				log.Printf("Warning: Invalid parent ID %s for node %s, skipping parent", *node.ParentID, node.ID)
			} else {
				parentID = sql.NullInt32{Int32: int32(pid), Valid: true}
			}
		}

		err = txQueries.CreateIABTopic(ctx, db.CreateIABTopicParams{
			ID:       int32(nodeID),
			Name:     node.Name,
			ParentID: parentID,
			Tier:     int32(node.Tier),
			Type:     sql.NullString{String: taxonomyType, Valid: true},
		})
		if err != nil {
			log.Printf("Warning: Failed to insert node %s (%s): %v", node.ID, node.Name, err)
			continue
		}
		count++
	}

	if err := tx.Commit(); err != nil {
		return 0, fmt.Errorf("failed to commit taxonomy: %w", err)
	}

	log.Printf("Inserted %d %s taxonomy nodes", count, taxonomyType)
	return count, nil
}

func (s *TaxonomyService) loadMappings(ctx context.Context) error {
	contentToProduct, err := s.loadMappingFile("data/content_to_ad_product_taxonomy_mapping.json")
	if err != nil {
		return fmt.Errorf("failed to load content-to-product mapping: %w", err)
	}

	productToContent, err := s.loadMappingFile("data/ad_product_to_content_taxonomy_mapping.json")
	if err != nil {
		return fmt.Errorf("failed to load product-to-content mapping: %w", err)
	}

	log.Printf("Loaded %d content->product mappings and %d product->content mappings", len(contentToProduct), len(productToContent))

	tx, err := s.db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer func(tx *sql.Tx) {
		err := tx.Rollback()
		if err != nil {
			log.Printf("Warning: Failed to rollback transaction: %v", err)
		}
	}(tx)

	txQueries := s.queries.WithTx(tx)

	insertCount := 0

	for contentIDStr, productIDStr := range contentToProduct {
		contentID, err := strconv.ParseInt(contentIDStr, 10, 32)
		if err != nil {
			log.Printf("Warning: Invalid content ID %s, skipping", contentIDStr)
			continue
		}

		productID, err := strconv.ParseInt(productIDStr, 10, 32)
		if err != nil {
			log.Printf("Warning: Invalid product ID %s, skipping", productIDStr)
			continue
		}

		err = txQueries.CreateIABTopicMapping(ctx, db.CreateIABTopicMappingParams{
			ContentTopicID: int32(contentID),
			ProductTopicID: int32(productID),
		})
		if err != nil {
			log.Printf("Warning: Failed to insert mapping %s -> %s: %v", contentIDStr, productIDStr, err)
			continue
		}
		insertCount++
	}

	for productIDStr, contentIDStr := range productToContent {
		productID, err := strconv.ParseInt(productIDStr, 10, 32)
		if err != nil {
			continue
		}

		contentID, err := strconv.ParseInt(contentIDStr, 10, 32)
		if err != nil {
			continue
		}

		err = txQueries.CreateIABTopicMapping(ctx, db.CreateIABTopicMappingParams{
			ContentTopicID: int32(contentID),
			ProductTopicID: int32(productID),
		})
		if err != nil {
			continue
		}
		insertCount++
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit mappings: %w", err)
	}

	log.Printf("Inserted %d topic mappings", insertCount)
	return nil
}

func (s *TaxonomyService) loadMappingFile(filePath string) (map[string]string, error) {
	data, err := os.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read %s: %w", filePath, err)
	}

	var mappings map[string]string
	if err := json.Unmarshal(data, &mappings); err != nil {
		return nil, fmt.Errorf("failed to parse %s: %w", filePath, err)
	}

	return mappings, nil
}
