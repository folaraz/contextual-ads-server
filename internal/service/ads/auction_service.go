package ads

import (
	"fmt"
	"math"
	"sort"
	"strconv"
	"strings"

	"github.com/folaraz/contextual-ads-server/internal/cache"
	"github.com/folaraz/contextual-ads-server/internal/models"
	goredis "github.com/redis/go-redis/v9"
)

const (
	defaultFloorPriceCPM = 0.50
	defaultMockCTR       = 0.05
)

type AuctionService struct {
	taxonomyCache *cache.TaxonomyCache
	floorPrice    float64
	pacingService *PacingService
}

func NewAuctionService(redisClient *goredis.Client) *AuctionService {
	return &AuctionService{
		taxonomyCache: cache.GetTaxonomyCache(),
		floorPrice:    defaultFloorPriceCPM,
		pacingService: NewPacingService(redisClient),
	}
}

func (s *AuctionService) RunAuction(ads []models.AdVectorResult, pageContext models.PageContext) models.AuctionResult {
	if len(ads) == 0 {
		return models.AuctionResult{HasWinner: false}
	}

	mapping := s.taxonomyCache.GetMapping()

	campaignIDs := make([]int32, 0, len(ads))
	for _, ad := range ads {
		campaignIDs = append(campaignIDs, ad.Ad.CampaignID)
	}
	pacingMultipliers := s.pacingService.GetPacingMultipliers(campaignIDs)

	candidates, filteredByBudget := ScoreAdsWithParams(ads, pageContext, mapping, pacingMultipliers)

	if len(candidates) == 0 {
		return models.AuctionResult{
			HasWinner: false,
			Stats: models.AuctionStats{
				TotalCandidates:    len(ads),
				FilteredByBudget:   filteredByBudget,
				EligibleForAuction: 0,
			},
		}
	}

	result := RunSecondPriceAuction(candidates, s.floorPrice)
	result.Stats = models.AuctionStats{
		TotalCandidates:    len(ads),
		FilteredByBudget:   filteredByBudget,
		EligibleForAuction: len(candidates),
	}
	return result
}

func CalculateECPM(ad models.Ad, predictedCTR float64) float64 {
	bidAmount := float64(ad.BidAmountCents) / 100.0

	switch ad.PricingModel {
	case models.CPC:
		return bidAmount * predictedCTR * 1000
	default:
		return bidAmount
	}
}

func ScoreAdsWithParams(ads []models.AdVectorResult, pageContext models.PageContext, mapping cache.TaxonomyMapping,
	pacingMultipliers map[int32]float64) ([]models.AuctionCandidate, int) {

	candidates := make([]models.AuctionCandidate, 0, len(ads))
	filteredByBudget := 0

	pageTopics := pageContext.Topics
	pageKeywords := pageContext.Keywords
	pageEntities := pageContext.Entities
	hasPageEntities := len(pageEntities) > 0

	for _, ad := range ads {
		adData := ad.Ad
		pacingMultiplier := pacingMultipliers[adData.CampaignID]
		if pacingMultiplier <= 0 {
			filteredByBudget++
			continue
		}

		// Convert ad targeting to maps for scoring
		adKeywords := keywordsToMap(adData.Keywords)
		adTopics := topicsToMap(adData.Topics)
		adEntities := entitiesToMap(adData.Entities)

		// Calculate component scores
		keywordScore := CalculateKeywordScore(adKeywords, pageKeywords)
		topicScore := CalculateTopicScore(adTopics, pageTopics, mapping)
		entityScore := CalculateEntityScore(adEntities, pageEntities)

		qualityScore := CalculateQualityScore(
			keywordScore, topicScore, entityScore, ad.VectorScore,
			hasPageEntities, adData.PricingModel,
		)

		// Calculate eCPM
		predictedCTR := defaultMockCTR
		eCPM := CalculateECPM(adData, predictedCTR)

		finalScore := math.Pow(eCPM, 0.4) * math.Pow(math.Max(qualityScore, 1e-6), 0.6) * pacingMultiplier

		candidates = append(candidates, models.AuctionCandidate{
			Ad:             adData,
			PacingScore:    pacingMultiplier,
			Similarity:     ad.VectorScore,
			PredictedCTR:   predictedCTR,
			QualityScore:   qualityScore,
			EffectiveBid:   eCPM,
			FinalRankScore: finalScore,
		})
	}

	return candidates, filteredByBudget
}

func RunSecondPriceAuction(candidates []models.AuctionCandidate, floorPrice float64) models.AuctionResult {
	if len(candidates) == 0 {
		return models.AuctionResult{HasWinner: false}
	}

	// Sort ads by final rank score, then eCPM, then quality score
	sort.SliceStable(candidates, func(i, j int) bool {
		if candidates[i].FinalRankScore == candidates[j].FinalRankScore {
			if candidates[i].EffectiveBid == candidates[j].EffectiveBid {
				return candidates[i].QualityScore > candidates[j].QualityScore
			}
			return candidates[i].EffectiveBid > candidates[j].EffectiveBid
		}
		return candidates[i].FinalRankScore > candidates[j].FinalRankScore
	})

	winner := candidates[0]
	winnerBid := float64(winner.Ad.BidAmountCents) / 100.0

	var clearingPrice float64
	if len(candidates) > 1 {
		secondPlace := candidates[1]
		denominator := winner.QualityScore * winner.PacingScore
		if denominator > 0 {
			clearingPrice = secondPlace.FinalRankScore / denominator
		} else {
			clearingPrice = winner.EffectiveBid
		}
		clearingPrice += 0.01
	} else {
		clearingPrice = floorPrice
	}

	finalClearingPrice := 0.0

	switch winner.Ad.PricingModel {
	case models.CPC:
		predictedCTR := winner.PredictedCTR
		if predictedCTR > 0 {
			finalClearingPrice = clearingPrice / (predictedCTR * 1000)
		} else {
			finalClearingPrice = winnerBid
		}
	default:
		finalClearingPrice = clearingPrice
	}

	finalClearingPrice = math.Min(finalClearingPrice, winnerBid)

	var runnerUps []models.AuctionCandidate
	if len(candidates) > 1 {
		runnerUps = candidates[1:]
	}

	return models.AuctionResult{
		Winner:    &winner,
		RunnerUps: runnerUps,
		PricePaid: finalClearingPrice,
		HasWinner: true,
	}
}

func keywordsToMap(keywords []models.KeywordTarget) map[string]float64 {
	m := make(map[string]float64, len(keywords))
	for _, k := range keywords {
		m[k.Keyword] = k.RelevanceScore
	}
	return m
}

func topicsToMap(topics []models.TopicTarget) map[string]models.Topic {
	m := make(map[string]models.Topic, len(topics))
	for _, t := range topics {
		m[strconv.Itoa(int(t.TopicID))] = models.Topic{
			Tier:           t.Tier,
			RelevanceScore: t.RelevanceScore,
		}
	}
	return m
}

func entitiesToMap(entities []models.EntityTarget) map[string]string {
	m := make(map[string]string, len(entities))
	for _, e := range entities {
		m[e.EntityID] = e.EntityType
	}
	return m
}

func CalculateKeywordScore(adKeywords, pageKeywords map[string]float64) float64 {
	if len(adKeywords) == 0 || len(pageKeywords) == 0 {
		return 0.0
	}

	pageKeywordsLower := make(map[string]float64, len(pageKeywords))
	for k, v := range pageKeywords {
		pageKeywordsLower[strings.ToLower(k)] = v
	}

	var totalWeight, matchedScore float64
	for kw, weight := range adKeywords {
		totalWeight += weight
		if pageWeight, exists := pageKeywordsLower[strings.ToLower(kw)]; exists {
			matchedScore += weight * pageWeight
		}
	}

	if totalWeight == 0 {
		return 0.0
	}

	score := math.Min(matchedScore/totalWeight, 1.0)
	return Normalize(len(pageKeywords), len(adKeywords), score)
}

func CalculateTopicScore(adTopics map[string]models.Topic, pageTopics map[string]models.Topic,
	mapping cache.TaxonomyMapping) float64 {
	if len(adTopics) == 0 || len(pageTopics) == 0 {
		return 0.0
	}

	topicWeight := func(t models.Topic) float64 {
		return t.RelevanceScore * (1.0 + float64(t.Tier)*0.5)
	}

	var pageWeight, adWeight, matchedWeight float64

	for _, t := range pageTopics {
		pageWeight += topicWeight(t)
	}

	for adIabId, adTopic := range adTopics {
		weight := topicWeight(adTopic)
		adWeight += weight

		matched := false
		// Primary: use ProductToContent taxonomy mapping
		if targetPageId, ok := mapping.ProductToContent[adIabId]; ok {
			if pageTopic, exists := pageTopics[targetPageId]; exists {
				matchedWeight += weight * pageTopic.RelevanceScore
				matched = true
			}
		}
		// Fallback: direct ID match
		if !matched {
			if pageTopic, exists := pageTopics[adIabId]; exists {
				matchedWeight += weight * pageTopic.RelevanceScore * 0.5
			}
		}
	}

	totalWeight := pageWeight + adWeight - matchedWeight
	if totalWeight <= 0 {
		return 0.0
	}

	return matchedWeight / totalWeight
}

func CalculateEntityScore(adEntities map[string]string, pageEntities []models.Entity) float64 {
	if len(adEntities) == 0 {
		return 0.0
	}

	// Build page entity index from slice
	pageIndex := make(map[string]string, len(pageEntities))
	pageTokens := make(map[string][]string)

	for _, entity := range pageEntities {
		lower := strings.ToLower(strings.TrimSpace(entity.Text))
		pageIndex[lower] = entity.Type

		for _, word := range strings.Fields(lower) {
			if len(word) > 2 {
				pageTokens[word] = append(pageTokens[word], entity.Type)
			}
		}
	}

	// Count matches
	var matched float64
	for entity, adType := range adEntities {
		lower := strings.ToLower(strings.TrimSpace(entity))

		// Exact match
		if pageType, exists := pageIndex[lower]; exists && pageType == adType {
			matched++
			continue
		}

		// Token match
		if types, exists := pageTokens[lower]; exists {
			for _, t := range types {
				if t == adType {
					matched++
					break
				}
			}
		}
	}

	if matched == 0 {
		return 0.0
	}

	coverage := matched / float64(len(adEntities))
	return Normalize(len(pageEntities), len(adEntities), coverage)
}

func CalculateQualityScore(keywordScore, topicScore, entityScore, similarityScore float64,
	hasPageEntities bool, strategy models.Strategy) float64 {
	var wKey, wTopic, wEntity, wSim float64

	switch strategy {
	case models.CPM:
		wKey, wTopic, wEntity, wSim = 0.15, 0.35, 0.10, 0.40
	case models.CPC:
		wKey, wTopic, wEntity, wSim = 0.20, 0.30, 0.40, 0.10
	default:
		fmt.Println("Unknown strategy, using default weights")
		wKey, wTopic, wEntity, wSim = 0.20, 0.30, 0.30, 0.20
	}

	if !hasPageEntities {
		wSim += wEntity
		wEntity = 0
	}

	score := (keywordScore * wKey) + (topicScore * wTopic) + (entityScore * wEntity) + (similarityScore * wSim)

	return score
}

func Normalize(pageLen int, adLen int, score float64) float64 {
	if pageLen <= adLen || adLen == 0 {
		return 1.0 * score
	}
	ratio := float64(pageLen) / float64(adLen)
	return (1.0 / (1.0 + 0.5*math.Log10(ratio))) * score
}
