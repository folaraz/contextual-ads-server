//go:build nlp_eval

package relevance

import (
	"sort"
	"testing"
	"time"

	"github.com/folaraz/contextual-ads-server/internal/cache"
	"github.com/folaraz/contextual-ads-server/internal/models"
	"github.com/folaraz/contextual-ads-server/internal/service/ads"
	evaluation "github.com/folaraz/contextual-ads-server/tests/evaluation"
	evalfixtures "github.com/folaraz/contextual-ads-server/tests/evaluation/fixtures"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

type nlpEvalResult struct {
	allResults  []PageEvalResult
	pageDetails []evaluation.PageDetail
	agg         AggregateResults
}

func runNLPRankingEval(
	t *testing.T,
	pages []evalfixtures.GeneratedPage,
	nlpAds []evalfixtures.NLPGeneratedAd,
	gt evalfixtures.GroundTruth,
	mapping cache.TaxonomyMapping,
) nlpEvalResult {
	t.Helper()

	adByID := make(map[int32]evalfixtures.NLPGeneratedAd, len(nlpAds))
	for _, ga := range nlpAds {
		adByID[ga.Ad.AdID] = ga
	}

	for _, page := range pages {
		relCount := gt.CountRelevant(page.PageContext.PageURLHash)
		titleSnippet := page.PageContext.Metadata.Title
		if len(titleSnippet) > 50 {
			titleSnippet = titleSnippet[:50]
		}
		t.Logf("  Page [%s] %q → %d relevant ads, %d keywords, %d entities, %d topics",
			page.Category, titleSnippet,
			relCount, len(page.PageContext.Keywords),
			len(page.PageContext.Entities), len(page.PageContext.Topics))
	}

	pacingMultipliers := make(map[int32]float64, len(nlpAds))
	for _, ga := range nlpAds {
		pacingMultipliers[ga.Ad.CampaignID] = 1.0
	}

	const detailTopK = 10

	var allResults []PageEvalResult
	var pageDetails []evaluation.PageDetail

	for _, page := range pages {
		pageLabels := gt[page.PageContext.PageURLHash]
		relevantCount := gt.CountRelevant(page.PageContext.PageURLHash)
		if relevantCount == 0 {
			t.Logf("  Skipping page %q (no relevant ads)", page.Category)
			continue
		}

		adVectorResults := make([]models.AdVectorResult, len(nlpAds))
		vectorScoreByAdID := make(map[int32]float64, len(nlpAds))
		for i, ga := range nlpAds {
			vectorScore := evalfixtures.CosineSimilarity(
				page.PageContext.PageEmbedding,
				ga.AdEmbedding,
			)

			adVectorResults[i] = models.AdVectorResult{
				Ad:          ga.Ad,
				VectorScore: vectorScore,
			}
			vectorScoreByAdID[ga.Ad.AdID] = vectorScore
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

		topN := detailTopK
		if topN > len(candidates) {
			topN = len(candidates)
		}
		topAds := make([]evaluation.RankedAdDetail, topN)
		for j := 0; j < topN; j++ {
			c := candidates[j]
			adInfo := adByID[c.Ad.AdID]
			topAds[j] = evaluation.RankedAdDetail{
				Rank:           j + 1,
				AdID:           c.Ad.AdID,
				Headline:       c.Ad.Headline,
				Industry:       adInfo.Industry,
				IsRelevant:     relevant[c.Ad.AdID],
				VectorScore:    vectorScoreByAdID[c.Ad.AdID],
				QualityScore:   c.QualityScore,
				FinalRankScore: c.FinalRankScore,
				EffectiveBid:   c.EffectiveBid,
			}
		}

		pageDetails = append(pageDetails, evaluation.PageDetail{
			PageHash:      page.PageContext.PageURLHash,
			Title:         page.PageContext.Metadata.Title,
			URL:           page.PageContext.Metadata.URL,
			Category:      page.Category,
			NumKeywords:   len(page.PageContext.Keywords),
			NumEntities:   len(page.PageContext.Entities),
			NumTopics:     len(page.PageContext.Topics),
			TotalRelevant: relevantCount,
			TotalAds:      len(candidates),
			PrecisionAt1:  p1,
			PrecisionAt3:  p3,
			PrecisionAt5:  p5,
			PrecisionAt10: p10,
			NDCGAt5:       ndcg5,
			NDCGAt10:      ndcg10,
			QualityGap:    relAvg - irrelAvg,
			TopAds:        topAds,
		})
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

	t.Log(evaluation.PrintDetailedNLPReport(pageDetails, detailTopK))

	t.Log(evaluation.PrintRelevanceReport(relevanceReport, evaluation.NLPRelevanceThresholds()))

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

	return nlpEvalResult{
		allResults:  allResults,
		pageDetails: pageDetails,
		agg:         agg,
	}
}

func TestRankingQuality_HeuristicGroundTruth(t *testing.T) {
	mapping, err := evalfixtures.LoadTaxonomyMapping()
	require.NoError(t, err, "Failed to load taxonomy mapping")

	pages, err := evalfixtures.LoadNLPPageContexts()
	require.NoError(t, err, "Failed to load NLP page contexts — run 'make eval-fixtures' first")
	require.NotEmpty(t, pages, "No NLP page contexts loaded")
	t.Logf("Loaded %d NLP-processed pages", len(pages))

	nlpAds, err := evalfixtures.LoadNLPAdContexts()
	require.NoError(t, err, "Failed to load NLP ad contexts — run 'make eval-fixtures' first")
	require.NotEmpty(t, nlpAds, "No NLP ad contexts loaded")
	t.Logf("Loaded %d NLP-processed ads", len(nlpAds))

	gt := evalfixtures.BuildGroundTruthHybrid(pages, nlpAds, 5, 1, 0.5, mapping)

	t.Log("\n========== NLP EVALUATION — Heuristic Ground Truth ==========")
	res := runNLPRankingEval(t, pages, nlpAds, gt, mapping)

	assert.Greater(t, res.agg.MeanPrecisionAt1, 0.15,
		"Mean Precision@1 should exceed 0.15 with heuristic ground truth (50 ads)")
	assert.Greater(t, res.agg.MeanNDCGAt5, 0.20,
		"Mean NDCG@5 should exceed 0.20 with heuristic ground truth")
	assert.Greater(t, res.agg.MeanQualityGap, 0.0,
		"Heuristic ground truth should produce a positive quality gap")
}

func TestRankingQuality_AnnotationGroundTruth(t *testing.T) {
	mapping, err := evalfixtures.LoadTaxonomyMapping()
	require.NoError(t, err, "Failed to load taxonomy mapping")

	pages, err := evalfixtures.LoadNLPPageContexts()
	require.NoError(t, err, "Failed to load NLP page contexts — run 'make eval-fixtures' first")
	require.NotEmpty(t, pages, "No NLP page contexts loaded")
	t.Logf("Loaded %d NLP-processed pages", len(pages))

	nlpAds, err := evalfixtures.LoadNLPAdContexts()
	require.NoError(t, err, "Failed to load NLP ad contexts — run 'make eval-fixtures' first")
	require.NotEmpty(t, nlpAds, "No NLP ad contexts loaded")
	t.Logf("Loaded %d NLP-processed ads", len(nlpAds))

	gt, err := evalfixtures.LoadManualAnnotations()
	if err != nil {
		t.Skipf("Skipping: failed to load annotations: %v", err)
	}
	if gt == nil || len(gt) == 0 {
		t.Skip("Skipping: no annotations file found (data/eval/annotations.json) — run 'make eval-annotations'")
	}
	t.Logf("Loaded %d pages of LLM/human annotations", len(gt))

	t.Log("\n========== NLP EVALUATION — Annotation Ground Truth ==========")
	res := runNLPRankingEval(t, pages, nlpAds, gt, mapping)

	assert.Greater(t, res.agg.MeanPrecisionAt1, 0.15,
		"Mean Precision@1 should exceed 0.15 with annotation ground truth")
	assert.Greater(t, res.agg.MeanNDCGAt5, 0.20,
		"Mean NDCG@5 should exceed 0.20 with annotation ground truth")
	assert.Greater(t, res.agg.MeanQualityGap, 0.0,
		"Annotation ground truth should produce a positive quality gap")
}

func TestEmbeddingClusteringQuality(t *testing.T) {
	pages, err := evalfixtures.LoadNLPPageContexts()
	require.NoError(t, err, "Failed to load NLP page contexts — run 'make eval-fixtures' first")
	require.NotEmpty(t, pages)

	nlpAds, err := evalfixtures.LoadNLPAdContexts()
	require.NoError(t, err, "Failed to load NLP ad contexts — run 'make eval-fixtures' first")
	require.NotEmpty(t, nlpAds)

	pagesByIndustry := make(map[string][]evalfixtures.GeneratedPage)
	for _, p := range pages {
		pagesByIndustry[p.Category] = append(pagesByIndustry[p.Category], p)
	}

	var intraSum, interSum float64
	var intraCount, interCount int

	for _, ad := range nlpAds {
		if len(ad.AdEmbedding) == 0 {
			continue
		}

		for industry, industryPages := range pagesByIndustry {
			for _, page := range industryPages {
				if len(page.PageContext.PageEmbedding) == 0 {
					continue
				}

				sim := evalfixtures.CosineSimilarity(page.PageContext.PageEmbedding, ad.AdEmbedding)

				if industry == ad.Industry {
					intraSum += sim
					intraCount++
				} else {
					interSum += sim
					interCount++
				}
			}
		}
	}

	if intraCount == 0 || interCount == 0 {
		t.Skip("Not enough data for clustering analysis")
	}

	intraMean := intraSum / float64(intraCount)
	interMean := interSum / float64(interCount)

	t.Logf("Intra-industry mean cosine similarity: %.4f (n=%d)", intraMean, intraCount)
	t.Logf("Inter-industry mean cosine similarity: %.4f (n=%d)", interMean, interCount)
	t.Logf("Clustering gap: %.4f", intraMean-interMean)

	assert.Greater(t, intraMean, interMean,
		"Intra-industry similarity should be higher than inter-industry similarity — "+
			"NLP embeddings should cluster by topic")
}
