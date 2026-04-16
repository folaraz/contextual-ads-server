package fixtures

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/folaraz/contextual-ads-server/internal/cache"
)

type GroundTruth map[string]map[int32]bool

func BuildGroundTruth(pages []GeneratedPage, ads []GeneratedAd, minKeywordOverlap int) GroundTruth {
	gt := make(GroundTruth, len(pages))

	for _, page := range pages {
		pageLabels := make(map[int32]bool, len(ads))

		pageKWSet := make(map[string]bool, len(page.PageContext.Keywords))
		for kw := range page.PageContext.Keywords {
			pageKWSet[strings.ToLower(kw)] = true
		}

		for _, ad := range ads {
			sameCategory := ad.Industry == page.Category

			overlap := 0
			for _, kw := range ad.Ad.Keywords {
				if pageKWSet[strings.ToLower(kw.Keyword)] {
					overlap++
				}
			}

			pageLabels[ad.Ad.AdID] = sameCategory && overlap >= minKeywordOverlap
		}

		gt[page.PageContext.PageURLHash] = pageLabels
	}

	return gt
}

func BuildGroundTruthHybrid(
	pages []GeneratedPage,
	ads []NLPGeneratedAd,
	minKeywordOverlap int,
	minTopicOverlap int,
	embeddingThreshold float64,
	taxonomyMapping cache.TaxonomyMapping,
) GroundTruth {
	gt := make(GroundTruth, len(pages))

	for _, page := range pages {
		pageLabels := make(map[int32]bool, len(ads))

		pageKWSet := make(map[string]bool, len(page.PageContext.Keywords))
		for kw := range page.PageContext.Keywords {
			pageKWSet[strings.ToLower(kw)] = true
		}

		pageContentTopicIDs := make(map[string]bool, len(page.PageContext.Topics))
		for id := range page.PageContext.Topics {
			pageContentTopicIDs[id] = true
		}

		pageProductTopicIDs := make(map[string]bool, len(page.PageContext.Topics))
		for id := range page.PageContext.Topics {
			if productID, ok := taxonomyMapping.ContentToProduct[id]; ok {
				pageProductTopicIDs[productID] = true
			}
		}

		for _, ad := range ads {
			sameCategory := ad.Industry == page.Category

			overlap := 0
			for _, kw := range ad.Ad.Keywords {
				if pageKWSet[strings.ToLower(kw.Keyword)] {
					overlap++
				}
			}

			topicOverlap := 0
			for _, t := range ad.Ad.Topics {
				adProductID := strconv.Itoa(int(t.TopicID))

				if contentID, ok := taxonomyMapping.ProductToContent[adProductID]; ok {
					if pageContentTopicIDs[contentID] {
						topicOverlap++
						continue
					}
				}

				if pageProductTopicIDs[adProductID] {
					topicOverlap++
				}
			}

			structuralRelevant := sameCategory && (overlap >= minKeywordOverlap || topicOverlap >= minTopicOverlap)

			semanticRelevant := false
			if len(page.PageContext.PageEmbedding) > 0 && len(ad.AdEmbedding) > 0 {
				sim := CosineSimilarity(page.PageContext.PageEmbedding, ad.AdEmbedding)
				semanticRelevant = sim >= embeddingThreshold
			}

			pageLabels[ad.Ad.AdID] = structuralRelevant || semanticRelevant
		}

		gt[page.PageContext.PageURLHash] = pageLabels
	}

	return gt
}

func (gt GroundTruth) CountRelevant(pageHash string) int {
	labels, ok := gt[pageHash]
	if !ok {
		return 0
	}
	count := 0
	for _, isRelevant := range labels {
		if isRelevant {
			count++
		}
	}
	return count
}

func LoadManualAnnotations() (GroundTruth, error) {
	evalDir := findEvalDataDir()
	path := filepath.Join(evalDir, "annotations.json")

	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, fmt.Errorf("reading annotations from %s: %w", path, err)
	}

	var raw map[string]map[string]bool
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, fmt.Errorf("parsing annotations: %w", err)
	}

	gt := make(GroundTruth, len(raw))
	for pageHash, adLabels := range raw {
		labels := make(map[int32]bool, len(adLabels))
		for adIDStr, relevant := range adLabels {
			adID, err := strconv.Atoi(adIDStr)
			if err != nil {
				continue
			}
			labels[int32(adID)] = relevant
		}
		gt[pageHash] = labels
	}

	return gt, nil
}

func (gt GroundTruth) MergeAnnotations(manual GroundTruth) {

	if manual == nil {
		return
	}
	for pageHash, manualLabels := range manual {
		if _, ok := gt[pageHash]; !ok {
			gt[pageHash] = make(map[int32]bool)
		}
		for adID, relevant := range manualLabels {
			gt[pageHash][adID] = relevant
		}
	}
}
