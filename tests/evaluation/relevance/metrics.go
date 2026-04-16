package relevance

import (
	"math"

	"github.com/folaraz/contextual-ads-server/internal/models"
)

func PrecisionAtK(ranked []models.AuctionCandidate, relevant map[int32]bool, k int) float64 {
	if k <= 0 || len(ranked) == 0 {
		return 0.0
	}
	if k > len(ranked) {
		k = len(ranked)
	}

	hits := 0
	for i := 0; i < k; i++ {
		if relevant[ranked[i].Ad.AdID] {
			hits++
		}
	}
	return float64(hits) / float64(k)
}

func NDCGAtK(ranked []models.AuctionCandidate, relevant map[int32]bool, k int) float64 {
	if k <= 0 || len(ranked) == 0 {
		return 0.0
	}
	if k > len(ranked) {
		k = len(ranked)
	}

	dcg := 0.0
	for i := 0; i < k; i++ {
		rel := 0.0
		if relevant[ranked[i].Ad.AdID] {
			rel = 1.0
		}
		dcg += rel / math.Log2(float64(i+2))
	}

	totalRelevant := 0
	for _, isRel := range relevant {
		if isRel {
			totalRelevant++
		}
	}
	if totalRelevant == 0 {
		return 0.0
	}

	idcg := 0.0
	relevantLeft := totalRelevant
	for i := 0; i < k && relevantLeft > 0; i++ {
		idcg += 1.0 / math.Log2(float64(i+2))
		relevantLeft--
	}

	if idcg == 0 {
		return 0.0
	}

	return dcg / idcg
}

func MeanRelevanceScore(candidates []models.AuctionCandidate,
	relevant map[int32]bool) (relevantAvg, irrelevantAvg float64) {
	var relSum, irrelSum float64
	var relCount, irrelCount int

	for _, c := range candidates {
		if relevant[c.Ad.AdID] {
			relSum += c.QualityScore
			relCount++
		} else {
			irrelSum += c.QualityScore
			irrelCount++
		}
	}

	if relCount > 0 {
		relevantAvg = relSum / float64(relCount)
	}
	if irrelCount > 0 {
		irrelevantAvg = irrelSum / float64(irrelCount)
	}
	return
}

type PageEvalResult struct {
	PageHash        string
	Category        string
	PrecisionAt1    float64
	PrecisionAt3    float64
	PrecisionAt5    float64
	PrecisionAt10   float64
	NDCGAt5         float64
	NDCGAt10        float64
	RelevantAvgQS   float64
	IrrelevantAvgQS float64
	QualityGap      float64
	TotalCandidates int
	TotalRelevant   int
}

type AggregateResults struct {
	MeanPrecisionAt1  float64
	MeanPrecisionAt3  float64
	MeanPrecisionAt5  float64
	MeanPrecisionAt10 float64
	MeanNDCGAt5       float64
	MeanNDCGAt10      float64
	MeanQualityGap    float64
	TotalPages        int
	TotalAds          int
	PerCategory       map[string][]PageEvalResult

	CeilingPrecisionAt1  float64
	CeilingPrecisionAt5  float64
	CeilingPrecisionAt10 float64
}

func precisionCeiling(totalRelevant, k int) float64 {
	if k <= 0 {
		return 0
	}
	r := totalRelevant
	if r > k {
		r = k
	}
	return float64(r) / float64(k)
}

func Aggregate(results []PageEvalResult) AggregateResults {
	agg := AggregateResults{
		PerCategory: make(map[string][]PageEvalResult),
	}
	if len(results) == 0 {
		return agg
	}

	agg.TotalPages = len(results)

	for _, r := range results {
		agg.MeanPrecisionAt1 += r.PrecisionAt1
		agg.MeanPrecisionAt3 += r.PrecisionAt3
		agg.MeanPrecisionAt5 += r.PrecisionAt5
		agg.MeanPrecisionAt10 += r.PrecisionAt10
		agg.MeanNDCGAt5 += r.NDCGAt5
		agg.MeanNDCGAt10 += r.NDCGAt10
		agg.MeanQualityGap += r.QualityGap
		agg.TotalAds = r.TotalCandidates
		agg.PerCategory[r.Category] = append(agg.PerCategory[r.Category], r)

		agg.CeilingPrecisionAt1 += precisionCeiling(r.TotalRelevant, 1)
		agg.CeilingPrecisionAt5 += precisionCeiling(r.TotalRelevant, 5)
		agg.CeilingPrecisionAt10 += precisionCeiling(r.TotalRelevant, 10)
	}

	n := float64(len(results))
	agg.MeanPrecisionAt1 /= n
	agg.MeanPrecisionAt3 /= n
	agg.MeanPrecisionAt5 /= n
	agg.MeanPrecisionAt10 /= n
	agg.MeanNDCGAt5 /= n
	agg.MeanNDCGAt10 /= n
	agg.MeanQualityGap /= n
	agg.CeilingPrecisionAt1 /= n
	agg.CeilingPrecisionAt5 /= n
	agg.CeilingPrecisionAt10 /= n

	return agg
}
