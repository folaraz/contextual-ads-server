package evaluation

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

type EvalReport struct {
	Timestamp time.Time        `json:"timestamp"`
	Duration  string           `json:"duration"`
	Relevance *RelevanceReport `json:"relevance,omitempty"`
	Auction   *AuctionReport   `json:"auction,omitempty"`
	Pacing    *PacingReport    `json:"pacing,omitempty"`
}

type RelevanceReport struct {
	AdCount           int                       `json:"ad_count"`
	PageCount         int                       `json:"page_count"`
	MeanPrecisionAt1  float64                   `json:"mean_precision_at_1"`
	MeanPrecisionAt5  float64                   `json:"mean_precision_at_5"`
	MeanPrecisionAt10 float64                   `json:"mean_precision_at_10"`
	MeanNDCGAt5       float64                   `json:"mean_ndcg_at_5"`
	MeanNDCGAt10      float64                   `json:"mean_ndcg_at_10"`
	MeanQualityGap    float64                   `json:"mean_quality_gap"`
	PerCategory       map[string]CategoryReport `json:"per_category"`

	CeilingPrecisionAt1  float64 `json:"ceiling_precision_at_1,omitempty"`
	CeilingPrecisionAt5  float64 `json:"ceiling_precision_at_5,omitempty"`
	CeilingPrecisionAt10 float64 `json:"ceiling_precision_at_10,omitempty"`
}

type RelevanceThresholds struct {
	PrecisionAt1  float64
	PrecisionAt5  float64
	PrecisionAt10 float64
	NDCGAt5       float64
	NDCGAt10      float64
}

func DefaultRelevanceThresholds() RelevanceThresholds {
	return RelevanceThresholds{
		PrecisionAt1:  0.60,
		PrecisionAt5:  0.50,
		PrecisionAt10: 0.40,
		NDCGAt5:       0.50,
		NDCGAt10:      0.40,
	}
}

func NLPRelevanceThresholds() RelevanceThresholds {
	return RelevanceThresholds{
		PrecisionAt1:  0.40,
		PrecisionAt5:  0.30,
		PrecisionAt10: 0.20,
		NDCGAt5:       0.50,
		NDCGAt10:      0.40,
	}
}

type CategoryReport struct {
	PageCount    int     `json:"page_count"`
	PrecisionAt1 float64 `json:"precision_at_1"`
	PrecisionAt5 float64 `json:"precision_at_5"`
	NDCGAt5      float64 `json:"ndcg_at_5"`
	QualityGap   float64 `json:"quality_gap"`
}

type AuctionReport struct {
	TestsRun    int  `json:"tests_run"`
	TestsPassed int  `json:"tests_passed"`
	AllPassed   bool `json:"all_passed"`
}

type PacingReport struct {
	Campaigns           []CampaignPacingReport `json:"campaigns"`
	MeanBudgetUtilError float64                `json:"mean_budget_utilization_error"`
	MeanOverSpendRatio  float64                `json:"mean_over_spend_ratio"`
	MeanMultiplierCV    float64                `json:"mean_multiplier_cv"`
}

type CampaignPacingReport struct {
	CampaignID            int32     `json:"campaign_id"`
	TotalBudget           float64   `json:"total_budget"`
	TotalSpend            float64   `json:"total_spend"`
	TotalUtilizationPct   float64   `json:"total_utilization_pct"`
	TotalUtilizationError float64   `json:"total_utilization_error"`
	DailyBudget           float64   `json:"daily_budget"`
	DailySpend            float64   `json:"daily_spend"`
	DailyUtilizationPct   float64   `json:"daily_utilization_pct"`
	DailyUtilizationError float64   `json:"daily_utilization_error"`
	OverSpendRatio        float64   `json:"over_spend_ratio"`
	MultiplierCV          float64   `json:"multiplier_cv"`
	MultiplierHistory     []float64 `json:"multiplier_history"`
	SpendCurve            []float64 `json:"spend_curve"`
}

func WriteReport(report EvalReport, outputDir string) (string, error) {
	if err := os.MkdirAll(outputDir, 0o755); err != nil {
		return "", fmt.Errorf("creating output dir: %w", err)
	}

	path := filepath.Join(outputDir, "eval_report.json")

	data, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return "", fmt.Errorf("marshaling report: %w", err)
	}

	if err := os.WriteFile(path, data, 0o644); err != nil {
		return "", fmt.Errorf("writing report: %w", err)
	}

	return path, nil
}

func PrintRelevanceReport(r *RelevanceReport, thresholds ...RelevanceThresholds) string {
	th := DefaultRelevanceThresholds()
	if len(thresholds) > 0 {
		th = thresholds[0]
	}

	var b strings.Builder

	b.WriteString("\n========== RELEVANCE EVALUATION REPORT ==========\n")
	b.WriteString(fmt.Sprintf("Ads: %d    Pages: %d\n\n", r.AdCount, r.PageCount))

	b.WriteString("--- Aggregate Metrics ---\n")
	b.WriteString(fmt.Sprintf("  Mean Precision@1:   %s\n", fmtMetricWithCeiling(r.MeanPrecisionAt1, th.PrecisionAt1, r.CeilingPrecisionAt1)))
	b.WriteString(fmt.Sprintf("  Mean Precision@5:   %s\n", fmtMetricWithCeiling(r.MeanPrecisionAt5, th.PrecisionAt5, r.CeilingPrecisionAt5)))
	b.WriteString(fmt.Sprintf("  Mean Precision@10:  %s\n", fmtMetricWithCeiling(r.MeanPrecisionAt10, th.PrecisionAt10, r.CeilingPrecisionAt10)))
	b.WriteString(fmt.Sprintf("  Mean NDCG@5:        %s\n", fmtMetric(r.MeanNDCGAt5, th.NDCGAt5)))
	b.WriteString(fmt.Sprintf("  Mean NDCG@10:       %s\n", fmtMetric(r.MeanNDCGAt10, th.NDCGAt10)))
	b.WriteString(fmt.Sprintf("  Mean Quality Gap:   %.4f\n\n", r.MeanQualityGap))

	b.WriteString("--- Per-Category Breakdown ---\n")
	b.WriteString(fmt.Sprintf("  %-15s  %6s  %6s  %7s  %8s  %5s\n",
		"Category", "P@1", "P@5", "NDCG@5", "QGap", "Pages"))
	b.WriteString(fmt.Sprintf("  %s\n", strings.Repeat("-", 60)))
	for cat, cr := range r.PerCategory {
		b.WriteString(fmt.Sprintf("  %-15s  %6.3f  %6.3f  %7.3f  %8.4f  %5d\n",
			cat, cr.PrecisionAt1, cr.PrecisionAt5, cr.NDCGAt5, cr.QualityGap, cr.PageCount))
	}
	b.WriteString("==================================================\n")

	return b.String()
}

func PrintPacingReport(r *PacingReport) string {
	var b strings.Builder

	b.WriteString("\n========== PACING EVALUATION REPORT ==========\n")
	b.WriteString(fmt.Sprintf("Campaigns: %d\n\n", len(r.Campaigns)))

	b.WriteString("--- Aggregate Metrics ---\n")
	b.WriteString(fmt.Sprintf("  Mean Daily Util Error:  %s\n", fmtMetric(1.0-r.MeanBudgetUtilError, 0.85)))
	b.WriteString(fmt.Sprintf("  Mean Over-Spend Ratio:  %.3f\n", r.MeanOverSpendRatio))
	b.WriteString(fmt.Sprintf("  Mean Multiplier CV:     %.4f\n\n", r.MeanMultiplierCV))

	b.WriteString("--- Per-Campaign Breakdown ---\n")
	header := fmt.Sprintf("  %-6s  %12s  %12s  %9s  %10s  %12s  %12s  %9s  %10s  %8s",
		"ID", "TotalBudget", "TotalSpend", "TotalUtil", "TotalErr", "DailyBudget", "DailySpend", "DailyUtil", "DailyErr", "MultCV")
	b.WriteString(header + "\n")
	b.WriteString(fmt.Sprintf("  %s\n", strings.Repeat("-", len(header)-2)))
	for _, c := range r.Campaigns {
		b.WriteString(fmt.Sprintf("  %-6d  $%11.2f  $%11.2f  %8.1f%%  %9.3f  $%11.2f  $%11.2f  %8.1f%%  %9.3f  %8.4f\n",
			c.CampaignID,
			c.TotalBudget, c.TotalSpend, c.TotalUtilizationPct*100, c.TotalUtilizationError,
			c.DailyBudget, c.DailySpend, c.DailyUtilizationPct*100, c.DailyUtilizationError,
			c.MultiplierCV))
	}
	b.WriteString("================================================\n")

	return b.String()
}

func fmtMetric(value, threshold float64) string {
	status := "PASS"
	if value < threshold {
		status = "FAIL"
	}
	return fmt.Sprintf("%.3f  [%s, threshold=%.2f]", value, status, threshold)
}

func fmtMetricWithCeiling(value, threshold, ceiling float64) string {
	if ceiling > 0 && ceiling < threshold {
		pct := value / ceiling * 100
		return fmt.Sprintf("%.3f  [%.0f%% of ceiling=%.3f, threshold=%.2f unreachable]", value, pct, ceiling, threshold)
	}
	return fmtMetric(value, threshold)
}

func FindReportsDir() string {
	_, filename, _, _ := runtime.Caller(0)
	return filepath.Join(filepath.Dir(filename), "reports")
}

func CreateRunDir(ts time.Time) (string, error) {
	dir := filepath.Join(FindReportsDir(), ts.Format("20060102_150405"))
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", fmt.Errorf("creating run dir: %w", err)
	}
	return dir, nil
}

type RankedAdDetail struct {
	Rank           int
	AdID           int32
	Headline       string
	Industry       string
	IsRelevant     bool
	VectorScore    float64
	QualityScore   float64
	FinalRankScore float64
	EffectiveBid   float64
}

type PageDetail struct {
	PageHash      string
	Title         string
	URL           string
	Category      string
	NumKeywords   int
	NumEntities   int
	NumTopics     int
	TotalRelevant int
	TotalAds      int

	PrecisionAt1  float64
	PrecisionAt3  float64
	PrecisionAt5  float64
	PrecisionAt10 float64
	NDCGAt5       float64
	NDCGAt10      float64
	QualityGap    float64

	TopAds []RankedAdDetail
}

func PrintDetailedNLPReport(pages []PageDetail, topK int) string {
	var b strings.Builder

	b.WriteString("\n")
	b.WriteString("==========================================================================\n")
	b.WriteString("       DETAILED PER-PAGE RANKING RESULTS (NLP Evaluation)                 \n")
	b.WriteString("==========================================================================\n")
	b.WriteString(fmt.Sprintf("  Pages evaluated: %d    Top-K shown: %d\n\n", len(pages), topK))

	for i, pg := range pages {
		title := pg.Title
		if len(title) > 70 {
			title = title[:67] + "..."
		}
		url := pg.URL
		if len(url) > 80 {
			url = url[:77] + "..."
		}

		b.WriteString(fmt.Sprintf("-- Page %d/%d ---------------------------------------------------------------\n", i+1, len(pages)))
		b.WriteString(fmt.Sprintf("|  Title:    %s\n", title))
		b.WriteString(fmt.Sprintf("|  URL:      %s\n", url))
		b.WriteString(fmt.Sprintf("|  Category: %-15s  Hash: %s\n", pg.Category, pg.PageHash))
		b.WriteString(fmt.Sprintf("|  Signals:  %d keywords, %d entities, %d topics\n",
			pg.NumKeywords, pg.NumEntities, pg.NumTopics))
		b.WriteString(fmt.Sprintf("|  Ground Truth: %d relevant ads out of %d total\n",
			pg.TotalRelevant, pg.TotalAds))
		b.WriteString("|\n")

		b.WriteString(fmt.Sprintf("|  Metrics:  P@1=%.3f  P@3=%.3f  P@5=%.3f  P@10=%.3f\n",
			pg.PrecisionAt1, pg.PrecisionAt3, pg.PrecisionAt5, pg.PrecisionAt10))
		b.WriteString(fmt.Sprintf("|            NDCG@5=%.3f  NDCG@10=%.3f  QGap=%.4f\n",
			pg.NDCGAt5, pg.NDCGAt10, pg.QualityGap))
		b.WriteString("|\n")

		n := topK
		if n > len(pg.TopAds) {
			n = len(pg.TopAds)
		}

		b.WriteString(fmt.Sprintf("|  Top %d Ranked Ads:\n", n))
		b.WriteString("|  " + fmt.Sprintf("%-4s  %-5s  %-3s  %-40s  %-12s  %8s  %8s  %8s  %8s\n",
			"Rank", "AdID", "Rel", "Headline", "Industry", "VecSim", "QScore", "RankScr", "eCPM"))
		b.WriteString("|  " + strings.Repeat("-", 110) + "\n")

		for j := 0; j < n; j++ {
			ad := pg.TopAds[j]
			relMarker := "  ."
			if ad.IsRelevant {
				relMarker = " **"
			}
			headline := ad.Headline
			if len(headline) > 40 {
				headline = headline[:37] + "..."
			}

			b.WriteString(fmt.Sprintf("|  #%-3d  %-5d  %s  %-40s  %-12s  %8.4f  %8.4f  %8.4f  %8.2f\n",
				ad.Rank, ad.AdID, relMarker, headline, ad.Industry,
				ad.VectorScore, ad.QualityScore, ad.FinalRankScore, ad.EffectiveBid))
		}

		relevantInTopK := 0
		for j := 0; j < n; j++ {
			if pg.TopAds[j].IsRelevant {
				relevantInTopK++
			}
		}
		if pg.TotalRelevant > relevantInTopK {
			b.WriteString(fmt.Sprintf("|  ... %d more relevant ad(s) ranked below position %d\n",
				pg.TotalRelevant-relevantInTopK, n))
		}

		b.WriteString("--------------------------------------------------------------------------\n\n")
	}

	return b.String()
}
