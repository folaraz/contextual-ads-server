package relevance

import (
	"testing"

	"github.com/folaraz/contextual-ads-server/internal/cache"
	"github.com/folaraz/contextual-ads-server/internal/models"
	"github.com/folaraz/contextual-ads-server/internal/service/ads"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

const defaultFloorPrice = 0.50

func makeCandidate(adID int32, bidCents int64, qualityScore, pacingScore float64, pricing models.Strategy) models.AuctionCandidate {
	ad := models.Ad{
		AdID:           adID,
		CampaignID:     adID,
		BidAmountCents: bidCents,
		PricingModel:   pricing,
	}
	eCPM := ads.CalculateECPM(ad, 0.05)
	return models.AuctionCandidate{
		Ad:             ad,
		PacingScore:    pacingScore,
		Similarity:     0.5,
		PredictedCTR:   0.05,
		QualityScore:   qualityScore,
		EffectiveBid:   eCPM,
		FinalRankScore: eCPM * qualityScore * pacingScore,
	}
}

func TestHighestBidderWins(t *testing.T) {
	candidates := []models.AuctionCandidate{
		makeCandidate(1, 200, 0.5, 1.0, models.CPM),
		makeCandidate(2, 400, 0.5, 1.0, models.CPM),
		makeCandidate(3, 600, 0.5, 1.0, models.CPM),
		makeCandidate(4, 800, 0.5, 1.0, models.CPM),
		makeCandidate(5, 1000, 0.5, 1.0, models.CPM),
	}

	result := ads.RunSecondPriceAuction(candidates, defaultFloorPrice)

	require.True(t, result.HasWinner, "Should have a winner")
	assert.Equal(t, int32(5), result.Winner.Ad.AdID, "Highest bidder ($10) should win")
	assert.Len(t, result.RunnerUps, 4, "Should have 4 runner-ups")
}

func TestSecondPriceMechanics(t *testing.T) {
	candidates := []models.AuctionCandidate{
		makeCandidate(1, 500, 0.5, 1.0, models.CPM),
		makeCandidate(2, 800, 0.5, 1.0, models.CPM),
	}

	result := ads.RunSecondPriceAuction(candidates, defaultFloorPrice)

	require.True(t, result.HasWinner)
	assert.Equal(t, int32(2), result.Winner.Ad.AdID, "Higher bidder should win")

	winnerBid := float64(result.Winner.Ad.BidAmountCents) / 100.0
	assert.Less(t, result.PricePaid, winnerBid,
		"Second-price: winner should pay less than their bid")

	assert.Greater(t, result.PricePaid, 0.0, "Price should be positive")
}

func TestFloorPriceWithSingleBidder(t *testing.T) {
	candidates := []models.AuctionCandidate{
		makeCandidate(1, 800, 0.5, 1.0, models.CPM),
	}

	result := ads.RunSecondPriceAuction(candidates, defaultFloorPrice)

	require.True(t, result.HasWinner)
	assert.Equal(t, int32(1), result.Winner.Ad.AdID)
	assert.InDelta(t, defaultFloorPrice, result.PricePaid, 0.01,
		"Single bidder should pay floor price ($0.50)")
}

func TestQualityOverridesBid(t *testing.T) {
	candidates := []models.AuctionCandidate{
		makeCandidate(1, 500, 0.9, 1.0, models.CPM),
		makeCandidate(2, 800, 0.2, 1.0, models.CPM),
	}

	result := ads.RunSecondPriceAuction(candidates, defaultFloorPrice)

	require.True(t, result.HasWinner)
	assert.Equal(t, int32(1), result.Winner.Ad.AdID,
		"Lower bid with higher quality should win when finalScore is higher")
}

func TestPacingMultiplierFiltering(t *testing.T) {
	adVectorResults := []models.AdVectorResult{
		{Ad: models.Ad{AdID: 1, CampaignID: 1, BidAmountCents: 500, PricingModel: models.CPM, Keywords: []models.KeywordTarget{{Keyword: "tech", RelevanceScore: 1.0}}}, VectorScore: 0.5},
		{Ad: models.Ad{AdID: 2, CampaignID: 2, BidAmountCents: 800, PricingModel: models.CPM, Keywords: []models.KeywordTarget{{Keyword: "tech", RelevanceScore: 1.0}}}, VectorScore: 0.5},
	}

	pageCtx := models.PageContext{
		Keywords: map[string]float64{"tech": 1.0},
	}

	pacing := map[int32]float64{
		1: 1.0,
		2: 0.0,
	}

	mapping := emptyMapping()
	candidates, filteredByBudget := ads.ScoreAdsWithParams(adVectorResults, pageCtx, mapping, pacing)

	assert.Equal(t, 1, filteredByBudget, "One ad should be filtered by budget")
	assert.Len(t, candidates, 1, "Only one candidate should remain")
	assert.Equal(t, int32(1), candidates[0].Ad.AdID, "Ad 1 should be the remaining candidate")
}

func TestBidTieBreaking(t *testing.T) {
	c1 := makeCandidate(1, 500, 0.5, 1.0, models.CPM)
	c2 := makeCandidate(2, 500, 0.6, 1.0, models.CPM)

	c1.FinalRankScore = 2.5
	c2.FinalRankScore = 2.5
	c1.EffectiveBid = 5.0
	c2.EffectiveBid = 5.0

	candidates := []models.AuctionCandidate{c1, c2}
	result := ads.RunSecondPriceAuction(candidates, defaultFloorPrice)

	require.True(t, result.HasWinner)
	assert.Equal(t, int32(2), result.Winner.Ad.AdID,
		"With equal finalScore and eCPM, higher quality should win")
}

func TestAuctionWithNoCandidates(t *testing.T) {
	result := ads.RunSecondPriceAuction(nil, defaultFloorPrice)
	assert.False(t, result.HasWinner, "No candidates should yield no winner")
}

func TestPricePaidNeverExceedsBid(t *testing.T) {
	candidates := []models.AuctionCandidate{
		makeCandidate(1, 300, 0.1, 1.0, models.CPM),
		makeCandidate(2, 1500, 0.8, 1.0, models.CPM),
	}

	result := ads.RunSecondPriceAuction(candidates, defaultFloorPrice)

	require.True(t, result.HasWinner)
	winnerBid := float64(result.Winner.Ad.BidAmountCents) / 100.0
	assert.LessOrEqual(t, result.PricePaid, winnerBid,
		"Price paid should never exceed winner's bid amount")
}

func emptyMapping() cache.TaxonomyMapping {
	return cache.TaxonomyMapping{
		ProductToContent: map[string]string{},
		ContentToProduct: map[string]string{},
	}
}
