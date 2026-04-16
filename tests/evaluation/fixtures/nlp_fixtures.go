package fixtures

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"

	"github.com/folaraz/contextual-ads-server/internal/models"
)

type nlpPageContext struct {
	PageURLHash   string              `json:"page_url_hash"`
	Keywords      map[string]float64  `json:"keywords"`
	Entities      []nlpEntity         `json:"entities"`
	Topics        map[string]nlpTopic `json:"topics"`
	PageEmbedding []float64           `json:"page_embedding"`
	ChunkContext  []nlpChunk          `json:"chunk_context"`
	Metadata      nlpPageMetadata     `json:"meta_data"`
	Theme         string              `json:"theme"`
	ProcessedAt   string              `json:"processed_at"`
}

type nlpEntity struct {
	Text string `json:"text"`
	Type string `json:"type"`
}

type nlpTopic struct {
	Name  string  `json:"name"`
	IabID string  `json:"iab_id"`
	Tier  int     `json:"tier"`
	Score float64 `json:"score"`
}

type nlpChunk struct {
	Content    string    `json:"content"`
	Embedding  []float64 `json:"embedding"`
	ChunkIndex int       `json:"chunk_index"`
}

type nlpPageMetadata struct {
	URL         string `json:"url"`
	Title       string `json:"title"`
	Description string `json:"description"`
}

type nlpAdContext struct {
	AdID            string              `json:"ad_id"`
	Keywords        map[string]float64  `json:"keywords"`
	Entities        []nlpEntity         `json:"entities"`
	Topics          map[string]nlpTopic `json:"topics"`
	Embedding       []float64           `json:"embedding"`
	ContentCategory string              `json:"content_category"`
	Headline        string              `json:"headline"`
	Description     string              `json:"description"`
	ProcessedAt     string              `json:"processed_at"`
}

type NLPGeneratedAd struct {
	GeneratedAd
	AdEmbedding []float32
}

func findEvalDataDir() string {
	_, filename, _, _ := runtime.Caller(0)
	projectRoot := filepath.Join(filepath.Dir(filename), "..", "..", "..")
	return filepath.Join(projectRoot, "data", "eval")
}

func LoadNLPPageContexts() ([]GeneratedPage, error) {
	evalDir := findEvalDataDir()
	path := filepath.Join(evalDir, "nlp_page_contexts.json")

	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("reading NLP page contexts from %s: %w", path, err)
	}

	var raw []nlpPageContext
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, fmt.Errorf("parsing NLP page contexts: %w", err)
	}

	pages := make([]GeneratedPage, 0, len(raw))
	for _, r := range raw {
		pageCtx := nlpPageToPageContext(r)

		industry, ok := ContentCategoryToIndustry[r.Theme]
		if !ok || industry == "" {
			industry = inferIndustryFromTopics(r.Topics)
		}
		if industry == "" {
			industry = inferIndustryFromURL(r.Metadata.URL)
		}

		pages = append(pages, GeneratedPage{
			PageContext: pageCtx,
			Category:    industry,
			SourceURL:   r.Metadata.URL,
		})
	}

	return pages, nil
}

func LoadNLPAdContexts() ([]NLPGeneratedAd, error) {
	evalDir := findEvalDataDir()
	path := filepath.Join(evalDir, "nlp_ad_contexts.json")

	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("reading NLP ad contexts from %s: %w", path, err)
	}

	var raw []nlpAdContext
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, fmt.Errorf("parsing NLP ad contexts: %w", err)
	}

	realAds, err := loadRealAds()
	if err != nil {
		return nil, fmt.Errorf("loading real ads for NLP overlay: %w", err)
	}

	realAdMap := make(map[string]GeneratedAd, len(realAds))
	for _, ga := range realAds {
		realAdMap[fmt.Sprintf("%03d", ga.Ad.AdID)] = ga
	}

	result := make([]NLPGeneratedAd, 0, len(raw))
	for _, r := range raw {
		ga, ok := realAdMap[r.AdID]
		if !ok {
			ga, ok = realAdMap[r.AdID]
			if !ok {
				continue
			}
		}

		ad := ga.Ad

		nlpKeywords := make([]models.KeywordTarget, 0, len(r.Keywords))
		for kw, score := range r.Keywords {
			nlpKeywords = append(nlpKeywords, models.KeywordTarget{
				Keyword:        kw,
				RelevanceScore: score,
			})
		}
		ad.Keywords = nlpKeywords

		nlpEntities := make([]models.EntityTarget, 0, len(r.Entities))
		for _, e := range r.Entities {
			nlpEntities = append(nlpEntities, models.EntityTarget{
				EntityID:   e.Text,
				EntityType: e.Type,
			})
		}
		ad.Entities = nlpEntities

		nlpTopics := make([]models.TopicTarget, 0, len(r.Topics))
		for _, t := range r.Topics {
			topicID, _ := strconv.Atoi(t.IabID)
			nlpTopics = append(nlpTopics, models.TopicTarget{
				TopicID:        int32(topicID),
				Tier:           t.Tier,
				RelevanceScore: t.Score,
			})
		}
		ad.Topics = nlpTopics

		industry := mapContentCategoryToIndustry(r.ContentCategory)

		adEmbedding := float64sToFloat32s(r.Embedding)

		result = append(result, NLPGeneratedAd{
			GeneratedAd: GeneratedAd{
				Ad:       ad,
				Industry: industry,
			},
			AdEmbedding: adEmbedding,
		})
	}

	return result, nil
}

func nlpPageToPageContext(r nlpPageContext) models.PageContext {
	entities := make([]models.Entity, len(r.Entities))
	for i, e := range r.Entities {
		entities[i] = models.Entity{
			Text: e.Text,
			Type: e.Type,
		}
	}

	topics := make(map[string]models.Topic, len(r.Topics))
	for id, t := range r.Topics {
		topics[id] = models.Topic{
			IabID:          t.IabID,
			Name:           t.Name,
			Tier:           t.Tier,
			RelevanceScore: t.Score,
		}
	}

	pageEmbedding := float64sToFloat32s(r.PageEmbedding)

	chunks := make([]models.ChunkContext, len(r.ChunkContext))
	for i, c := range r.ChunkContext {
		chunkEmb := make([]float32, len(c.Embedding))
		for j, v := range c.Embedding {
			chunkEmb[j] = float32(v)
		}
		chunks[i] = models.ChunkContext{
			Content:   c.Content,
			Embedding: chunkEmb,
		}
	}

	return models.PageContext{
		PageURLHash:   r.PageURLHash,
		Keywords:      r.Keywords,
		Entities:      entities,
		Topics:        topics,
		PageEmbedding: pageEmbedding,
		ChunkContext:  chunks,
		Metadata: models.PageMetadata{
			URL:         r.Metadata.URL,
			Title:       r.Metadata.Title,
			Description: r.Metadata.Description,
		},
		ProcessedAt: r.ProcessedAt,
	}
}

func float64sToFloat32s(in []float64) []float32 {
	out := make([]float32, len(in))
	for i, v := range in {
		out[i] = float32(v)
	}
	return out
}

var iabTopicNameToIndustry = map[string]string{
	"Sports":                   "sports",
	"News and Politics":        "education",
	"Business and Finance":     "finance",
	"Personal Finance":         "finance",
	"Technology & Computing":   "technology",
	"Medical Health":           "healthcare",
	"Healthy Living":           "healthcare",
	"Travel":                   "travel",
	"Education":                "education",
	"Food & Drink":             "food-beverage",
	"Television":               "entertainment",
	"Movies":                   "entertainment",
	"Music and Audio":          "entertainment",
	"Pop Culture":              "entertainment",
	"Video Gaming":             "entertainment",
	"Hobbies & Interests":      "e-commerce",
	"Careers":                  "education",
	"Family and Relationships": "e-commerce",
	"Fine Art":                 "entertainment",
	"Science":                  "technology",
	"Events and Attractions":   "entertainment",
	"Religion & Spirituality":  "education",

	"Soccer":                "sports",
	"Tennis":                "sports",
	"Basketball":            "sports",
	"Football":              "sports",
	"Olympic Sports":        "sports",
	"Sporting Events":       "sports",
	"Summer Olympic Sports": "sports",
	"Swimming":              "sports",
	"Disabled Sports":       "sports",
	"Extreme Sports":        "sports",

	"Politics":           "education",
	"International News": "education",
	"Crime":              "education",
	"Law":                "education",

	"Economy":              "finance",
	"Business":             "finance",
	"Financial Assistance": "finance",
	"Frugal Living":        "finance",

	"Computing":               "technology",
	"Artificial Intelligence": "technology",

	"Pharmaceutical Drugs":    "healthcare",
	"Diseases and Conditions": "healthcare",
	"Senior Health":           "healthcare",
	"Wellness":                "healthcare",

	"Travel Locations": "travel",
	"Travel Type":      "travel",

	"Environment":         "technology",
	"Biological Sciences": "technology",

	"Drama TV": "entertainment",

	"News":                  "education",
	"Entertainment Content": "entertainment",
	"Feature":               "education",
}

func inferIndustryFromTopics(topics map[string]nlpTopic) string {
	var bestIndustry string
	var bestScore float64

	for _, t := range topics {
		industry, ok := iabTopicNameToIndustry[t.Name]
		if !ok {
			continue
		}
		if t.Score > bestScore || (t.Score == bestScore && t.Tier > 1) {
			bestScore = t.Score
			bestIndustry = industry
		}
	}

	return bestIndustry
}

var newsDomains = []string{
	"aljazeera.com", "bbc.com", "bbc.co.uk", "reuters.com", "apnews.com",
	"cnn.com", "theguardian.com", "nytimes.com", "washingtonpost.com",
}

var urlPathIndustryHints = map[string]string{
	"/sport":         "sports",
	"/sports":        "sports",
	"/news":          "education",
	"/opinion":       "education",
	"/opinions":      "education",
	"/politics":      "education",
	"/entertainment": "entertainment",
	"/tech":          "technology",
	"/technology":    "technology",
	"/business":      "finance",
	"/finance":       "finance",
	"/travel":        "travel",
	"/food":          "food-beverage",
	"/health":        "healthcare",
	"/lifestyle":     "fashion",
	"/fashion":       "fashion",
	"/auto":          "automotive",
	"/automotive":    "automotive",
}

func inferIndustryFromURL(url string) string {
	lower := strings.ToLower(url)

	for prefix, industry := range urlPathIndustryHints {
		if strings.Contains(lower, prefix+"/") || strings.HasSuffix(lower, prefix) {
			return industry
		}
	}

	for _, domain := range newsDomains {
		if strings.Contains(lower, domain) {
			return "education"
		}
	}

	return ""
}
