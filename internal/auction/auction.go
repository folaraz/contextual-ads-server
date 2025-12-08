package auction

import (
	"math"
	"sort"
	"strings"

	"github.com/folaraz/contextual-ads-server/internal/models"
	"github.com/folaraz/contextual-ads-server/internal/storage"
)

//Apply quick business filters:
//
//1. Geographic targeting:
//User in: US
//Keep only ads targeting US
//Filtered out: ~3,000 ads (targeting other countries)
//
//2. Budget check:
//Remove ads with depleted daily budget
//Filtered out: ~1,200 ads
//
//3. Frequency cap:
//User has seen ad_23456 (Monday.com) 5 times today
//If frequency cap = 5, remove it
//Filtered out: ~500 ads
//
//4. Brand safety:
//Check page content against brand blocklists
//Page is safe, no filtering needed

func RunAdAuction(ads []models.AdRankResult, pageContext models.PageContext) models.AuctionResult {

	adTaxonomyMapping := storage.GetAdMapping()

	auctionCandidates := make([]models.AuctionCandidate, 0, len(ads))

	pageTopics := pageContext.Topics
	pageKeywords := pageContext.Keywords
	pageEntities := pageContext.Entities

	hasPageEntities := len(pageEntities) > 0

	mockCTR := 0.05 // todo predictionService.Predict(adData, pageContext)

	for _, ad := range ads {
		adData := ad.Ad
		adContext := adData.AdContext

		similarityScore := ad.VectorScore

		keywordScore := calculateKeywordScore(adContext.Keywords, pageKeywords)
		topicScore := calculateTopicScore(pageTopics, adContext.Topics, adTaxonomyMapping)
		entityScore := calculateEntityScore(pageEntities, adContext.Entities)

		qualityScore := calculateQualityScore(
			keywordScore, topicScore, entityScore, similarityScore,
			hasPageEntities,
			adData.Strategy,
		)

		var eCPM float64
		if adData.Strategy == models.CPC {
			eCPM = adData.BidAmount * mockCTR * 1000 // Standardize to CPM (x1000)
		} else if adData.Strategy == models.CPA {
			// Assume average conversion rate of 2% for CPA to CPM conversion
			averageConversionRate := 0.02
			eCPM = adData.BidAmount * mockCTR * averageConversionRate * 1000
		} else {
			eCPM = adData.BidAmount // Already CPM
		}

		pacingFactor := calculatePacingFactor(adData)

		finalScore := eCPM * qualityScore * pacingFactor

		auctionCandidates = append(auctionCandidates, models.AuctionCandidate{
			Ad:           adData,
			Similarity:   similarityScore,
			PredictedCTR: mockCTR,
			QualityScore: qualityScore,
			//eCPM:           eCPM, //todo need to find a way to store eCPM in AuctionCandidate struct
			//PacingFactor:   pacingFactor,
			FinalRankScore: finalScore,
		})
	}

	auctionResult := runSecondPriceAuction(auctionCandidates, 0.50) // Floor price of $0.50 CPM

	return auctionResult
}

func runSecondPriceAuction(candidates []models.AuctionCandidate, floorPrice float64) models.AuctionResult {
	if len(candidates) == 0 {
		return models.AuctionResult{}
	}

	// 1. Sort (Unchanged - this is good)
	sort.SliceStable(candidates, func(i, j int) bool {
		if candidates[i].FinalRankScore == candidates[j].FinalRankScore {
			if candidates[i].EffectiveBid == candidates[j].EffectiveBid {
				return candidates[i].PredictedCTR > candidates[j].PredictedCTR
			}
			return candidates[i].EffectiveBid > candidates[j].EffectiveBid
		}
		return candidates[i].FinalRankScore > candidates[j].FinalRankScore
	})

	winner := candidates[0]
	var price float64

	if len(candidates) > 1 {
		secondPlace := candidates[1]

		rawPrice := secondPlace.FinalRankScore / winner.PredictedCTR

		price = rawPrice + 0.01

	} else {
		if floorPrice > 0 {
			price = floorPrice
		} else {
			price = winner.Ad.BidAmount
		}
	}

	//Safety Cap, Never charge more than the Winner's Bid
	if price > winner.Ad.BidAmount {
		price = winner.Ad.BidAmount
	}

	if price < floorPrice {
		price = floorPrice
	}

	expectedCost := price * winner.PredictedCTR
	// we ensure that there is enough budget, but this update to the remaining budget should be done only after the objective of the ad is met (click or impression)
	// some form of  Budget Manager service deducts money when the actual Impression/Click pixel fires.
	winner.Ad.RemainingBudget -= expectedCost

	return models.AuctionResult{
		Winner:    winner,
		PricePaid: price,
	}
}

func calculatePacingFactor(ad models.Ad) float64 {
	totalDailyBudget := ad.DailyBudget
	if totalDailyBudget == 0 {
		return 1.0
	}
	budgetSpentSoFarToday := ad.DailyBudgetSpend
	remainingBudget := totalDailyBudget - budgetSpentSoFarToday
	if remainingBudget <= 0 {
		return 0.0
	}

	return remainingBudget / totalDailyBudget

}

func calculateKeywordScore(adKeywords map[string]float64, pageKeywords map[string]float64) float64 {
	if len(adKeywords) == 0 || len(pageKeywords) == 0 {
		return 0.0
	}

	pageKeywordsLower := make(map[string]float64)
	for k, v := range pageKeywords {
		pageKeywordsLower[strings.ToLower(k)] = v
	}

	totalAdWeights := 0.0
	matchedAdScore := 0.0

	for adKw, adWeight := range adKeywords {
		totalAdWeights += adWeight

		if pageWeight, exists := pageKeywordsLower[strings.ToLower(adKw)]; exists {
			matchScore := adWeight * pageWeight
			matchedAdScore += matchScore
		}
	}

	if totalAdWeights == 0 {
		return 0.0
	}

	score := matchedAdScore / totalAdWeights

	if score > 1.0 {
		score = 1.0
	}

	pageLen := float64(len(pageKeywords))
	adLen := float64(len(adKeywords))
	noiseFactor := 1.0

	if pageLen > adLen {
		ratio := pageLen / adLen
		noiseFactor = 1.0 / (1.0 + math.Log10(ratio))
	}

	return score * noiseFactor
}

//bayesian normalization i.e essentially representing zeros in the input data, just making data points more realistic.

func calculateTopicScore(adTopics map[string]models.Topic, pageTopics map[string]models.Topic, mapping storage.AdTaxonomyMapping) float64 {
	if len(adTopics) == 0 || len(pageTopics) == 0 {
		return 0.0
	}

	getTopicWeight := func(t models.Topic) float64 {
		return t.Score * (1.0 + (float64(t.Tier) * 0.5))
	}

	pageWeight := 0.0
	for _, topic := range pageTopics {
		pageWeight += getTopicWeight(topic)
	}

	totalAdWeight := 0.0
	totalMatchedWeight := 0.0

	for adIabId, adTopic := range adTopics {
		weight := getTopicWeight(adTopic)
		totalAdWeight += weight

		if targetPageId, hasMapping := mapping.ProductToContent[adIabId]; hasMapping {

			if pageTopic, exists := pageTopics[targetPageId]; exists {
				matchedWeight := weight * pageTopic.Score
				totalMatchedWeight += matchedWeight
			}
		}
	}

	allWeight := pageWeight + totalAdWeight - totalMatchedWeight

	if allWeight <= 0 {
		return 0.0
	}

	return totalMatchedWeight / allWeight
}

func calculateEntityScore(pageEntities map[string]string, adEntities map[string]string) float64 {
	if len(adEntities) == 0 {
		return 0.0
	}

	// Build normalized page index
	pageTokens := make(map[string][]string)
	pageEntitiesLower := make(map[string]string)

	for entity, eType := range pageEntities {
		lowerEntity := strings.ToLower(strings.TrimSpace(entity))
		pageEntitiesLower[lowerEntity] = eType

		// Tokenize for partial matching
		for _, word := range strings.Fields(lowerEntity) {
			if len(word) > 2 {
				pageTokens[word] = append(pageTokens[word], eType)
			}
		}
	}

	// Calculate recall: how many ad entities did we find?
	matchedCount := 0.0

	for adEntity, adType := range adEntities {
		adEntityLower := strings.ToLower(strings.TrimSpace(adEntity))

		// Try exact match first
		if pageType, exists := pageEntitiesLower[adEntityLower]; exists && pageType == adType {
			matchedCount++
			continue
		}

		if types, exists := pageTokens[adEntityLower]; exists {
			for _, t := range types {
				if t == adType {
					matchedCount++
					break
				}
			}
		}
	}

	if matchedCount == 0 {
		return 0.0
	}

	coverageRatio := matchedCount / float64(len(adEntities))

	noiseFactor := 1.0
	pageLen := float64(len(pageEntities))
	adLen := float64(len(adEntities))

	if pageLen > adLen {
		ratio := pageLen / adLen
		noiseFactor = 1.0 / (1.0 + math.Log10(ratio))
	}

	return coverageRatio * noiseFactor
}

func calculateQualityScore(keywordScore, topicScore, entityScore, similarityScore float64, hasPageEntities bool, strategy models.Strategy) float64 {

	var wEntity, wTopic, wSim, wKey float64

	switch strategy {
	case models.CPM:
		wEntity = 0.10
		wKey = 0.10
		wTopic = 0.60
		wSim = 0.20

	case models.CPC:
		wEntity = 0.40
		wKey = 0.20
		wTopic = 0.30
		wSim = 0.10

	case models.CPA:
		wEntity = 0.50
		wKey = 0.25
		wTopic = 0.20
		wSim = 0.05

	default:
		wEntity = 0.30
		wKey = 0.20
		wTopic = 0.30
		wSim = 0.20
	}

	if !hasPageEntities {
		wSim += wEntity
		wEntity = 0.0
	}

	totalScore := (keywordScore * wKey) +
		(topicScore * wTopic) +
		(similarityScore * wSim) +
		(entityScore * wEntity)

	// Penalize low-topic relevance
	if topicScore < 0.1 {
		totalScore *= 0.5
	}

	return totalScore
}
