package relevance

import (
	"math/rand"
	"sort"
	"testing"
	"time"

	"github.com/folaraz/contextual-ads-server/internal/models"
	"github.com/folaraz/contextual-ads-server/internal/service/ads"
	evaluation "github.com/folaraz/contextual-ads-server/tests/evaluation"
	evalfixtures "github.com/folaraz/contextual-ads-server/tests/evaluation/fixtures"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestRankingQuality(t *testing.T) {
	mapping, err := evalfixtures.LoadTaxonomyMapping()
	require.NoError(t, err, "Failed to load taxonomy mapping")

	generatedAds, err := evalfixtures.LoadAds()
	require.NoError(t, err, "Failed to load ads inventory")
	t.Logf("Loaded %d ads across %d categories", len(generatedAds), len(evalfixtures.Categories))

	pages, err := evalfixtures.GeneratePages()
	require.NoError(t, err, "Failed to generate pages")
	t.Logf("Loaded %d pages", len(pages))

	gt := evalfixtures.BuildGroundTruth(pages, generatedAds, 2)

	for _, page := range pages {
		relCount := gt.CountRelevant(page.PageContext.PageURLHash)
		t.Logf("  Page [%s] %q → %d relevant ads, %d keywords",
			page.Category, page.PageContext.Metadata.Title[:min(50, len(page.PageContext.Metadata.Title))],
			relCount, len(page.PageContext.Keywords))
	}

	rng := rand.New(rand.NewSource(77))

	pacingMultipliers := make(map[int32]float64, len(generatedAds))
	for _, ga := range generatedAds {
		pacingMultipliers[ga.Ad.CampaignID] = 1.0
	}

	var allResults []PageEvalResult

	for _, page := range pages {
		pageLabels := gt[page.PageContext.PageURLHash]
		relevantCount := gt.CountRelevant(page.PageContext.PageURLHash)
		if relevantCount == 0 {
			t.Logf("  Skipping page %q (no relevant ads)", page.Category)
			continue
		}

		adVectorResults := make([]models.AdVectorResult, len(generatedAds))
		for i, ga := range generatedAds {
			var vectorScore float64
			if pageLabels[ga.Ad.AdID] {
				vectorScore = 0.55 + rng.Float64()*0.20
			} else {
				vectorScore = 0.25 + rng.Float64()*0.20
			}
			adVectorResults[i] = models.AdVectorResult{
				Ad:          ga.Ad,
				VectorScore: vectorScore,
			}
		}

		candidates, _ := ads.ScoreAdsWithParams(adVectorResults, page.PageContext, mapping, pacingMultipliers)

		sort.SliceStable(candidates, func(i, j int) bool {
			return candidates[i].FinalRankScore > candidates[j].FinalRankScore
		})

		relevant := pageLabels
		p1 := PrecisionAtK(candidates, relevant, 1)
		p3 := PrecisionAtK(candidates, relevant, 3)
		p5 := PrecisionAtK(candidates, relevant, 5)
		p10 := PrecisionAtK(candidates, relevant, 10)
		ndcg5 := NDCGAtK(candidates, relevant, 5)
		ndcg10 := NDCGAtK(candidates, relevant, 10)
		relAvg, irrelAvg := MeanRelevanceScore(candidates, relevant)

		result := PageEvalResult{
			PageHash:        page.PageContext.PageURLHash,
			Category:        page.Category,
			PrecisionAt1:    p1,
			PrecisionAt3:    p3,
			PrecisionAt5:    p5,
			PrecisionAt10:   p10,
			NDCGAt5:         ndcg5,
			NDCGAt10:        ndcg10,
			RelevantAvgQS:   relAvg,
			IrrelevantAvgQS: irrelAvg,
			QualityGap:      relAvg - irrelAvg,
			TotalCandidates: len(candidates),
			TotalRelevant:   relevantCount,
		}
		allResults = append(allResults, result)
	}

	require.NotEmpty(t, allResults, "Should have evaluation results")

	agg := Aggregate(allResults)

	perCategory := make(map[string]evaluation.CategoryReport, len(agg.PerCategory))
	for category, results := range agg.PerCategory {
		catAgg := Aggregate(results)
		perCategory[category] = evaluation.CategoryReport{
			PageCount:    len(results),
			PrecisionAt1: catAgg.MeanPrecisionAt1,
			PrecisionAt5: catAgg.MeanPrecisionAt5,
			NDCGAt5:      catAgg.MeanNDCGAt5,
			QualityGap:   catAgg.MeanQualityGap,
		}
	}

	relevanceReport := &evaluation.RelevanceReport{
		AdCount:              agg.TotalAds,
		PageCount:            agg.TotalPages,
		MeanPrecisionAt1:     agg.MeanPrecisionAt1,
		MeanPrecisionAt5:     agg.MeanPrecisionAt5,
		MeanPrecisionAt10:    agg.MeanPrecisionAt10,
		MeanNDCGAt5:          agg.MeanNDCGAt5,
		MeanNDCGAt10:         agg.MeanNDCGAt10,
		MeanQualityGap:       agg.MeanQualityGap,
		PerCategory:          perCategory,
		CeilingPrecisionAt1:  agg.CeilingPrecisionAt1,
		CeilingPrecisionAt5:  agg.CeilingPrecisionAt5,
		CeilingPrecisionAt10: agg.CeilingPrecisionAt10,
	}

	t.Log(evaluation.PrintRelevanceReport(relevanceReport))

	now := time.Now()
	runDir, err := evaluation.CreateRunDir(now)
	require.NoError(t, err)

	report := evaluation.EvalReport{
		Timestamp: now,
		Duration:  "N/A",
		Relevance: relevanceReport,
	}
	if path, err := evaluation.WriteReport(report, runDir); err != nil {
		t.Logf("Warning: failed to write report: %v", err)
	} else {
		t.Logf("Report written to %s", path)
	}

	assert.Greater(t, agg.MeanPrecisionAt1, 0.50,
		"Mean Precision@1 should exceed 0.50 (relevant ad ranks first at least half the time)")
	assert.Greater(t, agg.MeanNDCGAt5, 0.40,
		"Mean NDCG@5 should exceed 0.40")
	assert.Greater(t, agg.MeanQualityGap, 0.0,
		"Relevant ads should have higher quality scores than irrelevant ads on average")
}

func TestScoreOrderingConsistency(t *testing.T) {
	mapping, err := evalfixtures.LoadTaxonomyMapping()
	require.NoError(t, err)

	generatedAds, err := evalfixtures.LoadAds()
	require.NoError(t, err)

	pages, err := evalfixtures.GeneratePages()
	require.NoError(t, err)
	require.NotEmpty(t, pages)

	pacingMultipliers := make(map[int32]float64, len(generatedAds))
	for _, ga := range generatedAds {
		pacingMultipliers[ga.Ad.CampaignID] = 1.0
	}

	page := pages[0]
	adVectorResults := make([]models.AdVectorResult, len(generatedAds))
	for i, ga := range generatedAds {
		adVectorResults[i] = models.AdVectorResult{Ad: ga.Ad, VectorScore: 0.5}
	}

	candidates, _ := ads.ScoreAdsWithParams(adVectorResults, page.PageContext, mapping, pacingMultipliers)

	sort.SliceStable(candidates, func(i, j int) bool {
		return candidates[i].FinalRankScore > candidates[j].FinalRankScore
	})

	for i := 1; i < len(candidates); i++ {
		assert.GreaterOrEqual(t, candidates[i-1].FinalRankScore, candidates[i].FinalRankScore,
			"Candidates should be sorted by FinalRankScore descending")
	}

	for _, c := range candidates {
		assert.GreaterOrEqual(t, c.QualityScore, 0.0, "Quality score should be non-negative")
		assert.GreaterOrEqual(t, c.EffectiveBid, 0.0, "eCPM should be non-negative")
		assert.GreaterOrEqual(t, c.FinalRankScore, 0.0, "Final rank score should be non-negative")
	}
}
