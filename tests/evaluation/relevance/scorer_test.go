package relevance

import (
	"testing"

	"github.com/folaraz/contextual-ads-server/internal/cache"
	"github.com/folaraz/contextual-ads-server/internal/models"
	"github.com/folaraz/contextual-ads-server/internal/service/ads"
	"github.com/stretchr/testify/assert"
)

func TestKeywordScoring_ExactOverlap(t *testing.T) {
	adKW := map[string]float64{"shopping": 1.0, "deals": 1.0, "discount": 1.0}
	pageKW := map[string]float64{"shopping": 1.0, "deals": 1.0, "discount": 1.0}

	score := ads.CalculateKeywordScore(adKW, pageKW)
	assert.InDelta(t, 1.0, score, 0.01, "Exact overlap should yield score ~1.0")
}

func TestKeywordScoring_PartialOverlap(t *testing.T) {
	adKW := map[string]float64{"shopping": 1.0, "deals": 1.0, "discount": 1.0, "sale": 1.0}
	pageKW := map[string]float64{"shopping": 1.0, "deals": 1.0}

	score := ads.CalculateKeywordScore(adKW, pageKW)
	assert.Greater(t, score, 0.0, "Partial overlap should yield positive score")
	assert.Less(t, score, 1.0, "Partial overlap should be less than 1.0")
}

func TestKeywordScoring_NoOverlap(t *testing.T) {
	adKW := map[string]float64{"cars": 1.0, "vehicles": 1.0}
	pageKW := map[string]float64{"cooking": 1.0, "recipes": 1.0}

	score := ads.CalculateKeywordScore(adKW, pageKW)
	assert.Equal(t, 0.0, score, "No overlap should yield 0.0")
}

func TestKeywordScoring_EmptyInputs(t *testing.T) {
	assert.Equal(t, 0.0, ads.CalculateKeywordScore(nil, map[string]float64{"a": 1.0}))
	assert.Equal(t, 0.0, ads.CalculateKeywordScore(map[string]float64{"a": 1.0}, nil))
	assert.Equal(t, 0.0, ads.CalculateKeywordScore(nil, nil))
}

func TestKeywordScoring_WeightedOverlap(t *testing.T) {
	adKW := map[string]float64{"shopping": 0.9, "deals": 0.5}
	pageKW := map[string]float64{"shopping": 1.0, "deals": 0.3, "other": 1.0}

	score := ads.CalculateKeywordScore(adKW, pageKW)
	assert.Greater(t, score, 0.0, "Weighted overlap should produce positive score")
}

func TestTopicScoring_MatchingTopics(t *testing.T) {
	mapping := cache.TaxonomyMapping{
		ProductToContent: map[string]string{"1000": "100"},
		ContentToProduct: map[string]string{"100": "1000"},
	}

	adTopics := map[string]models.Topic{
		"1000": {Tier: 1, RelevanceScore: 0.8},
	}
	pageTopics := map[string]models.Topic{
		"100": {Tier: 1, RelevanceScore: 0.9},
	}

	score := ads.CalculateTopicScore(adTopics, pageTopics, mapping)
	assert.Greater(t, score, 0.0, "Matching topics via mapping should yield positive score")
}

func TestTopicScoring_NoMapping(t *testing.T) {
	mapping := cache.TaxonomyMapping{
		ProductToContent: map[string]string{},
		ContentToProduct: map[string]string{},
	}

	adTopics := map[string]models.Topic{
		"1000": {Tier: 1, RelevanceScore: 0.8},
	}
	pageTopics := map[string]models.Topic{
		"100": {Tier: 1, RelevanceScore: 0.9},
	}

	score := ads.CalculateTopicScore(adTopics, pageTopics, mapping)
	assert.Equal(t, 0.0, score, "Without mapping, topics should not match")
}

func TestTopicScoring_TierWeighting(t *testing.T) {
	mapping := cache.TaxonomyMapping{
		ProductToContent: map[string]string{"1000": "100"},
		ContentToProduct: map[string]string{"100": "1000"},
	}

	adTopicsTier1 := map[string]models.Topic{"1000": {Tier: 1, RelevanceScore: 0.8}}
	adTopicsTier3 := map[string]models.Topic{"1000": {Tier: 3, RelevanceScore: 0.8}}
	pageTopics := map[string]models.Topic{"100": {Tier: 1, RelevanceScore: 0.9}}

	score1 := ads.CalculateTopicScore(adTopicsTier1, pageTopics, mapping)
	score3 := ads.CalculateTopicScore(adTopicsTier3, pageTopics, mapping)

	assert.Greater(t, score3, score1, "Higher tier should produce higher score")
}

func TestTopicScoring_EmptyInputs(t *testing.T) {
	mapping := cache.TaxonomyMapping{ProductToContent: map[string]string{}, ContentToProduct: map[string]string{}}
	assert.Equal(t, 0.0, ads.CalculateTopicScore(nil, map[string]models.Topic{"1": {}}, mapping))
	assert.Equal(t, 0.0, ads.CalculateTopicScore(map[string]models.Topic{"1": {}}, nil, mapping))
}

func TestEntityScoring_ExactMatch(t *testing.T) {
	adEntities := map[string]string{"Nike": "BRAND", "Adidas": "BRAND"}
	pageEntities := []models.Entity{
		{Text: "Nike", Type: "BRAND"},
		{Text: "Adidas", Type: "BRAND"},
	}

	score := ads.CalculateEntityScore(adEntities, pageEntities)
	assert.InDelta(t, 1.0, score, 0.01, "Full exact match should yield ~1.0")
}

func TestEntityScoring_TokenMatch(t *testing.T) {
	adEntities := map[string]string{"nike": "BRAND"}
	pageEntities := []models.Entity{
		{Text: "Nike Running Shoes", Type: "BRAND"},
	}

	score := ads.CalculateEntityScore(adEntities, pageEntities)
	assert.Greater(t, score, 0.0, "Token match should yield positive score")
}

func TestEntityScoring_TypeMismatch(t *testing.T) {
	adEntities := map[string]string{"Nike": "PRODUCT"}
	pageEntities := []models.Entity{
		{Text: "Nike", Type: "BRAND"},
	}

	score := ads.CalculateEntityScore(adEntities, pageEntities)
	assert.Equal(t, 0.0, score, "Type mismatch should not count as match")
}

func TestEntityScoring_EmptyAd(t *testing.T) {
	score := ads.CalculateEntityScore(nil, []models.Entity{{Text: "Nike", Type: "BRAND"}})
	assert.Equal(t, 0.0, score, "Empty ad entities should yield 0.0")
}

func TestQualityScoreWeights_CPM(t *testing.T) {
	score := ads.CalculateQualityScore(1.0, 1.0, 1.0, 1.0, true, models.CPM)
	assert.InDelta(t, 1.0, score, 0.01, "All 1.0 inputs should yield 1.0")

	topicHeavy := ads.CalculateQualityScore(0.0, 1.0, 0.0, 0.0, true, models.CPM)
	keywordHeavy := ads.CalculateQualityScore(1.0, 0.0, 0.0, 0.0, true, models.CPM)
	assert.Greater(t, topicHeavy, keywordHeavy, "Topic score should matter more than keyword for CPM")
}

func TestQualityScoreWeights_CPC(t *testing.T) {
	entityHeavy := ads.CalculateQualityScore(0.0, 0.0, 1.0, 0.0, true, models.CPC)
	topicHeavy := ads.CalculateQualityScore(0.0, 1.0, 0.0, 0.0, true, models.CPC)
	assert.Greater(t, entityHeavy, topicHeavy, "Entity score should matter more than topic for CPC")
}

func TestQualityScoreWeights_NoEntities(t *testing.T) {
	withEntities := ads.CalculateQualityScore(0.5, 0.5, 0.0, 1.0, true, models.CPM)
	withoutEntities := ads.CalculateQualityScore(0.5, 0.5, 0.0, 1.0, false, models.CPM)
	assert.Greater(t, withoutEntities, withEntities,
		"Without entities, similarity weight should increase (entity weight → similarity)")
}

func TestNormalization_EqualLength(t *testing.T) {
	score := ads.Normalize(5, 5, 0.8)
	assert.InDelta(t, 0.8, score, 0.01, "Equal lengths should not penalize")
}

func TestNormalization_PageLarger(t *testing.T) {
	scorePenalized := ads.Normalize(20, 3, 0.8)
	scoreNormal := ads.Normalize(3, 3, 0.8)
	assert.Less(t, scorePenalized, scoreNormal,
		"Page with more attributes than ad should penalize score")
}

func TestNormalization_AdLarger(t *testing.T) {
	score := ads.Normalize(3, 10, 0.8)
	assert.InDelta(t, 0.8, score, 0.01, "Ad larger than page should not penalize")
}
