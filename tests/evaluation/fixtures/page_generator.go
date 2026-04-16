package fixtures

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/json"
	"fmt"
	"math"
	"math/rand"
	"os"
	"path/filepath"
	"strings"

	"github.com/folaraz/contextual-ads-server/internal/models"
)

type GeneratedPage struct {
	PageContext models.PageContext
	Category    string
	SourceURL   string
}

type crawledPage struct {
	URL     string   `json:"url"`
	Title   string   `json:"title"`
	Content string   `json:"content"`
	Theme   string   `json:"theme"`
	Tags    []string `json:"tags"`
}

const targetPagesPerIndustry = 9

func GeneratePages() ([]GeneratedPage, error) {
	rng := rand.New(rand.NewSource(99))

	crawled, err := loadCrawledPages()
	if err != nil {
		return nil, fmt.Errorf("loading crawled pages: %w", err)
	}

	ads, err := LoadAds()
	if err != nil {
		return nil, fmt.Errorf("loading ads for keyword pool: %w", err)
	}
	allKeywords := AllAdKeywords(ads)

	var pages []GeneratedPage
	industryPageCount := make(map[string]int)

	for url, cp := range crawled {
		industry, ok := ContentCategoryToIndustry[cp.Theme]
		if !ok {
			industry = cp.Theme
		}

		pageCtx := crawledPageToContext(rng, url, cp, allKeywords, industry)
		pages = append(pages, GeneratedPage{
			PageContext: pageCtx,
			Category:    industry,
			SourceURL:   url,
		})
		industryPageCount[industry]++
	}

	syntheticID := 10000
	for _, industry := range Industries {
		existing := industryPageCount[industry]
		needed := targetPagesPerIndustry - existing
		if needed <= 0 {
			continue
		}

		tmpl, ok := IndustryTemplates[industry]
		if !ok {
			continue
		}

		for i := 0; i < needed; i++ {
			pageCtx := generateSyntheticPage(rng, syntheticID, tmpl, allKeywords)
			pages = append(pages, GeneratedPage{
				PageContext: pageCtx,
				Category:    industry,
				SourceURL:   fmt.Sprintf("synthetic://%s/%d", industry, syntheticID),
			})
			syntheticID++
		}
	}

	return pages, nil
}

func crawledPageToContext(rng *rand.Rand, url string, cp crawledPage, adKeywords []string, industry string) models.PageContext {
	urlHash := hashString(url)
	contentLower := strings.ToLower(cp.Content + " " + cp.Title)

	keywords := make(map[string]float64)
	for _, kw := range adKeywords {
		if strings.Contains(contentLower, strings.ToLower(kw)) {
			keywords[kw] = 0.7 + rng.Float64()*0.3
		}
	}

	if tmpl, ok := IndustryTemplates[industry]; ok {
		for _, kw := range tmpl.Keywords {
			if strings.Contains(contentLower, strings.ToLower(kw)) {
				if _, exists := keywords[kw]; !exists {
					keywords[kw] = 0.6 + rng.Float64()*0.3
				}
			}
		}
	}

	var entities []models.Entity
	for _, kw := range adKeywords {
		titleCase := toTitleCase(kw)
		if strings.Contains(cp.Content, titleCase) && len(kw) > 2 {
			entities = append(entities, models.Entity{
				Text: titleCase,
				Type: "BRAND",
			})
		}
	}
	if len(entities) == 0 {
		titleWords := strings.Fields(cp.Title)
		for _, w := range titleWords {
			if len(w) > 3 && w[0] >= 'A' && w[0] <= 'Z' {
				entities = append(entities, models.Entity{
					Text: w,
					Type: "ORG",
				})
				if len(entities) >= 2 {
					break
				}
			}
		}
	}

	topics := make(map[string]models.Topic)

	embedding := deterministicEmbedding(industry, 384)

	return models.PageContext{
		PageURLHash:   urlHash,
		Keywords:      keywords,
		Entities:      entities,
		Topics:        topics,
		PageEmbedding: embedding,
		Metadata: models.PageMetadata{
			URL:         url,
			Title:       cp.Title,
			Description: truncate(cp.Content, 200),
		},
		ProcessedAt: "2026-01-01T00:00:00Z",
	}
}

func generateSyntheticPage(rng *rand.Rand, pageID int, tmpl IndustryTemplate, adKeywords []string) models.PageContext {
	syntheticURL := fmt.Sprintf("https://example.com/%s/article-%d", tmpl.Industry, pageID)
	urlHash := hashString(syntheticURL)

	numKeywords := 8 + rng.Intn(7)
	if numKeywords > len(tmpl.Keywords) {
		numKeywords = len(tmpl.Keywords)
	}
	kwIndices := rng.Perm(len(tmpl.Keywords))[:numKeywords]
	keywords := make(map[string]float64, numKeywords)
	for _, idx := range kwIndices {
		keywords[tmpl.Keywords[idx]] = 0.6 + rng.Float64()*0.4
	}

	noiseCount := 2 + rng.Intn(3)
	for i := 0; i < noiseCount && i < len(adKeywords); i++ {
		randKW := adKeywords[rng.Intn(len(adKeywords))]
		if _, exists := keywords[randKW]; !exists {
			keywords[randKW] = 0.3 + rng.Float64()*0.3
		}
	}

	numEntities := 1 + rng.Intn(3)
	if numEntities > len(tmpl.Entities) {
		numEntities = len(tmpl.Entities)
	}
	entIndices := rng.Perm(len(tmpl.Entities))[:numEntities]
	entities := make([]models.Entity, numEntities)
	for i, idx := range entIndices {
		entities[i] = models.Entity{
			Text: tmpl.Entities[idx],
			Type: tmpl.EntityTypes[idx],
		}
	}

	topics := make(map[string]models.Topic)
	embedding := deterministicEmbedding(tmpl.Industry, 384)

	headline := tmpl.HeadlineTemplates[rng.Intn(len(tmpl.HeadlineTemplates))]
	title := fmt.Sprintf("%s — %s Industry Insights", headline, toTitleCase(tmpl.Industry))

	return models.PageContext{
		PageURLHash:   urlHash,
		Keywords:      keywords,
		Entities:      entities,
		Topics:        topics,
		PageEmbedding: embedding,
		Metadata: models.PageMetadata{
			URL:         syntheticURL,
			Title:       title,
			Description: fmt.Sprintf("Synthetic page for %s industry evaluation.", tmpl.Industry),
		},
		ProcessedAt: "2026-01-01T00:00:00Z",
	}
}

func deterministicEmbedding(category string, dim int) []float32 {
	h := sha256.Sum256([]byte(category))
	seed := int64(binary.LittleEndian.Uint64(h[:8]))
	rng := rand.New(rand.NewSource(seed))

	embedding := make([]float32, dim)
	var norm float64
	for i := range embedding {
		v := float32(rng.NormFloat64())
		embedding[i] = v
		norm += float64(v * v)
	}
	norm = math.Sqrt(norm)
	for i := range embedding {
		embedding[i] /= float32(norm)
	}
	return embedding
}

func loadCrawledPages() (map[string]crawledPage, error) {
	dataDir := findDataDir()
	data, err := os.ReadFile(filepath.Join(dataDir, "crawled_pages.json"))
	if err != nil {
		return nil, err
	}

	var pages map[string]crawledPage
	if err := json.Unmarshal(data, &pages); err != nil {
		return nil, err
	}
	return pages, nil
}

func hashString(s string) string {
	h := sha256.Sum256([]byte(s))
	return fmt.Sprintf("%x", h[:16])
}

func truncate(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}

func toTitleCase(s string) string {
	words := strings.Fields(strings.ToLower(s))
	for i, w := range words {
		if len(w) > 0 {
			words[i] = strings.ToUpper(w[:1]) + w[1:]
		}
	}
	return strings.Join(words, " ")
}
