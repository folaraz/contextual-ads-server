package pacing

import (
	"encoding/json"
	"fmt"
	"math"
	"math/rand"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/folaraz/contextual-ads-server/internal/cache"
	"github.com/folaraz/contextual-ads-server/internal/models"
	"github.com/folaraz/contextual-ads-server/internal/service/ads"
	evaluation "github.com/folaraz/contextual-ads-server/tests/evaluation"
	evalfixtures "github.com/folaraz/contextual-ads-server/tests/evaluation/fixtures"
	goredis "github.com/redis/go-redis/v9"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

type pacingSnapshot struct {
	Interval   int
	CampaignID int32
	Multiplier float64
	SpendCents int64
	DailySpend int64
}

type campaignSetup struct {
	CampaignID   int32
	TotalBudget  float64
	DailyBudget  float64
	DurationDays int
}

func seedCampaignState(t *testing.T, mr *miniredis.Miniredis, cs campaignSetup) {
	t.Helper()
	now := time.Now().UTC()
	start := now.Add(-24 * time.Hour)
	end := start.Add(time.Duration(cs.DurationDays) * 24 * time.Hour)
	cid := strconv.Itoa(int(cs.CampaignID))

	stateKey := fmt.Sprintf("campaign:%s:state", cid)
	mr.HSet(stateKey,
		"campaign_id", cid,
		"advertiser_id", "1",
		"total_budget", fmt.Sprintf("%.2f", cs.TotalBudget),
		"daily_budget", fmt.Sprintf("%.2f", cs.DailyBudget),
		"start_time", strconv.FormatInt(start.Unix(), 10),
		"end_time", strconv.FormatInt(end.Unix(), 10),
		"status", "active",
		"current_multiplier", "1.0",
		"previous_multiplier", "1.0",
		"integral_sum", "0.0",
	)

	metricsKey := fmt.Sprintf("campaign:%s:metrics", cid)
	mr.HSet(metricsKey,
		"impressions", "0",
		"clicks", "0",
		"spend_cents", "0",
		"last_updated", strconv.FormatInt(now.Unix(), 10),
	)

	today := now.Format("2006-01-02")
	dailyKey := fmt.Sprintf("campaign:%s:daily:%s", cid, today)
	mr.HSet(dailyKey,
		"spend_cents", "0",
	)

	mr.SAdd("active_campaigns", cid)
}

func readMultiplier(mr *miniredis.Miniredis, campaignID int32) float64 {
	cid := strconv.Itoa(int(campaignID))
	key := fmt.Sprintf("campaign:%s:state", cid)
	val := mr.HGet(key, "current_multiplier")
	m, err := strconv.ParseFloat(val, 64)
	if err != nil {
		return 1.0
	}
	return m
}

func readSpendCents(mr *miniredis.Miniredis, campaignID int32) int64 {
	cid := strconv.Itoa(int(campaignID))
	key := fmt.Sprintf("campaign:%s:metrics", cid)
	val := mr.HGet(key, "spend_cents")
	v, _ := strconv.ParseInt(val, 10, 64)
	return v
}

func incrementSpend(mr *miniredis.Miniredis, campaignID int32, spendCents int64) {
	cid := strconv.Itoa(int(campaignID))

	metricsKey := fmt.Sprintf("campaign:%s:metrics", cid)
	mr.HIncrBy(metricsKey, "spend_cents", int(spendCents))
	mr.HIncrBy(metricsKey, "impressions", 1)
	mr.HSet(metricsKey, "last_updated", strconv.FormatInt(time.Now().Unix(), 10))

	today := time.Now().UTC().Format("2006-01-02")
	dailyKey := fmt.Sprintf("campaign:%s:daily:%s", cid, today)
	mr.HIncrBy(dailyKey, "spend_cents", int(spendCents))
}

func runPythonPacing(t *testing.T, redisURL string, campaignID int32, simTime ...float64) (float64, error) {
	t.Helper()
	pythonDir := findPythonDir()
	cliPath := filepath.Join(pythonDir, "pacing", "pacing_cli.py")

	args := []string{cliPath,
		"--redis-url", redisURL,
		"--campaign-id", strconv.Itoa(int(campaignID)),
	}
	if len(simTime) > 0 && simTime[0] > 0 {
		args = append(args, "--sim-time", fmt.Sprintf("%.3f", simTime[0]))
	}

	cmd := exec.Command("python3", args...)
	cmd.Dir = pythonDir

	output, err := cmd.CombinedOutput()
	if err != nil {
		return 0, fmt.Errorf("pacing CLI failed: %w\noutput: %s", err, string(output))
	}

	var result struct {
		Multiplier float64 `json:"multiplier"`
		Status     string  `json:"status"`
	}
	if err := json.Unmarshal(output, &result); err != nil {
		return 0, fmt.Errorf("parsing pacing output: %w\nraw: %s", err, string(output))
	}

	return result.Multiplier, nil
}

func runBatchPythonPacing(t *testing.T, redisURL string, campaignIDs []int32, simTime float64) (map[int32]float64,
	error) {
	t.Helper()
	pythonDir := findPythonDir()
	cliPath := filepath.Join(pythonDir, "pacing", "pacing_cli.py")

	idStrs := make([]string, len(campaignIDs))
	for i, cid := range campaignIDs {
		idStrs[i] = strconv.Itoa(int(cid))
	}

	args := []string{cliPath,
		"--redis-url", redisURL,
		"--campaign-ids", strings.Join(idStrs, ","),
	}
	if simTime > 0 {
		args = append(args, "--sim-time", fmt.Sprintf("%.3f", simTime))
	}

	cmd := exec.Command("python3", args...)
	cmd.Dir = pythonDir

	output, err := cmd.CombinedOutput()
	if err != nil {
		return nil, fmt.Errorf("batch pacing CLI failed: %w\noutput: %s", err, string(output))
	}

	var raw map[string]struct {
		Multiplier float64 `json:"multiplier"`
		Status     string  `json:"status"`
	}
	if err := json.Unmarshal(output, &raw); err != nil {
		return nil, fmt.Errorf("parsing batch pacing output: %w\nraw: %s", err, string(output))
	}

	result := make(map[int32]float64, len(raw))
	for cidStr, r := range raw {
		cid, _ := strconv.Atoi(cidStr)
		result[int32(cid)] = r.Multiplier
	}
	return result, nil
}

func findPythonDir() string {
	_, filename, _, _ := runtime.Caller(0)
	return filepath.Join(filepath.Dir(filename), "..", "..", "..", "python")
}

func TestMultiplierAffectsAuctionOutcome(t *testing.T) {

	adA := models.AdVectorResult{
		Ad: models.Ad{
			AdID: 1, CampaignID: 1, BidAmountCents: 500, PricingModel: models.CPM,
			Keywords: []models.KeywordTarget{{Keyword: "tech", RelevanceScore: 1.0}},
		},
		VectorScore: 0.5,
	}
	adB := models.AdVectorResult{
		Ad: models.Ad{
			AdID: 2, CampaignID: 2, BidAmountCents: 500, PricingModel: models.CPM,
			Keywords: []models.KeywordTarget{{Keyword: "tech", RelevanceScore: 1.0}},
		},
		VectorScore: 0.5,
	}

	pageCtx := models.PageContext{
		Keywords: map[string]float64{"tech": 1.0},
	}
	mapping := cache.TaxonomyMapping{
		ProductToContent: map[string]string{},
		ContentToProduct: map[string]string{},
	}

	pacing := map[int32]float64{1: 1.5, 2: 0.6}
	adVectors := []models.AdVectorResult{adA, adB}

	candidates, _ := ads.ScoreAdsWithParams(adVectors, pageCtx, mapping, pacing)
	sort.SliceStable(candidates, func(i, j int) bool {
		return candidates[i].FinalRankScore > candidates[j].FinalRankScore
	})

	require.Len(t, candidates, 2)
	assert.Equal(t, int32(1), candidates[0].Ad.AdID,
		"Campaign with higher pacing multiplier should rank first")
	assert.Greater(t, candidates[0].FinalRankScore, candidates[1].FinalRankScore)
}

type campaignAdSpec struct {
	BidCents       int64
	Keyword        string
	RelevanceScore float64
	VectorScore    float64
}

func TestClosedLoopPacingSimulation(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping closed-loop pacing simulation in short mode")
	}

	mr, err := miniredis.Run()
	require.NoError(t, err)
	defer mr.Close()

	redisURL := fmt.Sprintf("redis://%s", mr.Addr())

	testCmd := exec.Command("python3", "-c", "import redis; print('ok')")
	if err := testCmd.Run(); err != nil {
		t.Skipf("Python3 with redis package not available: %v", err)
	}

	campaigns := []campaignSetup{
		{CampaignID: 1, TotalBudget: 5_000, DailyBudget: 200, DurationDays: 7},
		{CampaignID: 2, TotalBudget: 25_000, DailyBudget: 500, DurationDays: 7},
		{CampaignID: 3, TotalBudget: 50_000, DailyBudget: 1_000, DurationDays: 7},

		{CampaignID: 5, TotalBudget: 10_000, DailyBudget: 400, DurationDays: 7},
		{CampaignID: 7, TotalBudget: 1_500, DailyBudget: 600, DurationDays: 3},
		{CampaignID: 8, TotalBudget: 500_000, DailyBudget: 800, DurationDays: 7},
		{CampaignID: 10, TotalBudget: 70_000, DailyBudget: 300, DurationDays: 7},
	}

	adSpecs := map[int32]campaignAdSpec{
		1:  {BidCents: 80, Keyword: "technology", RelevanceScore: 1.0, VectorScore: 0.50},
		2:  {BidCents: 100, Keyword: "technology", RelevanceScore: 1.0, VectorScore: 0.50},
		3:  {BidCents: 120, Keyword: "technology", RelevanceScore: 1.0, VectorScore: 0.50},
		5:  {BidCents: 500, Keyword: "technology", RelevanceScore: 1.0, VectorScore: 0.55},
		7:  {BidCents: 150, Keyword: "technology", RelevanceScore: 1.0, VectorScore: 0.50},
		8:  {BidCents: 110, Keyword: "technology", RelevanceScore: 1.0, VectorScore: 0.50},
		10: {BidCents: 75, Keyword: "technology", RelevanceScore: 0.85, VectorScore: 0.45},
	}

	for _, cs := range campaigns {
		seedCampaignState(t, mr, cs)
	}

	rng := rand.New(rand.NewSource(42))
	mapping, err := evalfixtures.LoadTaxonomyMapping()
	require.NoError(t, err)

	pages, err := evalfixtures.GeneratePages()
	require.NoError(t, err)
	require.NotEmpty(t, pages)

	testAds := make([]models.AdVectorResult, 0, len(campaigns)+10)
	for _, cs := range campaigns {
		spec := adSpecs[cs.CampaignID]
		testAds = append(testAds, models.AdVectorResult{
			Ad: models.Ad{
				AdID: cs.CampaignID, CampaignID: cs.CampaignID,
				BidAmountCents: spec.BidCents, PricingModel: models.CPM,
				Keywords: []models.KeywordTarget{{Keyword: spec.Keyword, RelevanceScore: spec.RelevanceScore}},
			},
			VectorScore: spec.VectorScore,
		})
	}

	for i := int32(100); i < 110; i++ {
		testAds = append(testAds, models.AdVectorResult{
			Ad: models.Ad{
				AdID: i, CampaignID: i, BidAmountCents: 50 + int64(rng.Intn(80)),
				PricingModel: models.CPM,
				Keywords:     []models.KeywordTarget{{Keyword: "technology", RelevanceScore: 0.5}},
			},
			VectorScore: 0.3,
		})
	}

	numIntervals := 3000
	requestsPerInterval := 8
	pacingEveryN := 2
	totalPacingCycles := numIntervals / pacingEveryN

	simDayStart := time.Now().UTC().Truncate(24 * time.Hour)
	secondsPerCycle := 86400.0 / float64(totalPacingCycles)

	var snapshots []pacingSnapshot

	redisClient := goredis.NewClient(&goredis.Options{Addr: mr.Addr()})
	defer redisClient.Close()

	campaignIDs := make([]int32, len(campaigns))
	for i, cs := range campaigns {
		campaignIDs[i] = cs.CampaignID
	}

	t.Logf("Starting closed-loop simulation: %d intervals, %d requests/interval, pacing every %d intervals (%d cycles), %d campaigns + %d background ads",
		numIntervals, requestsPerInterval, pacingEveryN, totalPacingCycles, len(campaigns), 10)

	pacingCycleIndex := 0
	for interval := 0; interval < numIntervals; interval++ {
		pacingMultipliers := make(map[int32]float64)
		for _, cs := range campaigns {
			pacingMultipliers[cs.CampaignID] = readMultiplier(mr, cs.CampaignID)
		}
		for i := int32(100); i < 110; i++ {
			pacingMultipliers[i] = 1.0
		}

		for r := 0; r < requestsPerInterval; r++ {
			page := pages[rng.Intn(len(pages))]
			candidates, _ := ads.ScoreAdsWithParams(testAds, page.PageContext, mapping, pacingMultipliers)
			if len(candidates) == 0 {
				continue
			}

			result := ads.RunSecondPriceAuction(candidates, 0.50)
			if !result.HasWinner {
				continue
			}

			winnerCID := result.Winner.Ad.CampaignID
			priceCents := int64(result.PricePaid * 100)
			if priceCents > 0 {
				incrementSpend(mr, winnerCID, priceCents)
			}
		}

		if (interval+1)%pacingEveryN == 0 {
			simTimeOffset := float64(simDayStart.Unix()) + float64(pacingCycleIndex)*secondsPerCycle
			pacingCycleIndex++

			batchResults, err := runBatchPythonPacing(t, redisURL, campaignIDs, simTimeOffset)
			if err != nil {
				t.Fatalf("Batch pacing failed at interval %d: %v", interval, err)
			}

			for _, cs := range campaigns {
				multiplier := batchResults[cs.CampaignID]
				spend := readSpendCents(mr, cs.CampaignID)

				snapshots = append(snapshots, pacingSnapshot{
					Interval:   interval,
					CampaignID: cs.CampaignID,
					Multiplier: multiplier,
					SpendCents: spend,
				})
			}
		}
	}

	var campaignReports []evaluation.CampaignPacingReport
	var totalUtilError, totalOverSpend, totalCV float64

	for _, cs := range campaigns {
		var campaignSnapshots []pacingSnapshot
		for _, s := range snapshots {
			if s.CampaignID == cs.CampaignID {
				campaignSnapshots = append(campaignSnapshots, s)
			}
		}

		if len(campaignSnapshots) == 0 {
			t.Logf("Campaign %d: no snapshots", cs.CampaignID)
			continue
		}

		finalSpend := readSpendCents(mr, cs.CampaignID)
		spendDollars := float64(finalSpend) / 100.0

		totalUtil := spendDollars / cs.TotalBudget
		totalUtilErr := math.Abs(1.0 - totalUtil)

		dailyUtil := spendDollars / cs.DailyBudget
		dailyUtilErr := math.Abs(1.0 - dailyUtil)

		overSpend := 0.0
		if spendDollars > cs.DailyBudget {
			overSpend = spendDollars / cs.DailyBudget
		}

		var multipliers []float64
		var spendCurve []float64
		for _, s := range campaignSnapshots {
			multipliers = append(multipliers, s.Multiplier)
			spendCurve = append(spendCurve, float64(s.SpendCents)/100.0)
		}

		var sumMult float64
		for _, m := range multipliers {
			sumMult += m
		}
		avgMult := sumMult / float64(len(multipliers))

		var sumSq float64
		for _, m := range multipliers {
			sumSq += (m - avgMult) * (m - avgMult)
		}
		cv := 0.0
		if avgMult > 0 {
			cv = math.Sqrt(sumSq/float64(len(multipliers))) / avgMult
		}

		campaignReports = append(campaignReports, evaluation.CampaignPacingReport{
			CampaignID:            cs.CampaignID,
			TotalBudget:           cs.TotalBudget,
			TotalSpend:            spendDollars,
			TotalUtilizationPct:   totalUtil,
			TotalUtilizationError: totalUtilErr,
			DailyBudget:           cs.DailyBudget,
			DailySpend:            spendDollars,
			DailyUtilizationPct:   dailyUtil,
			DailyUtilizationError: dailyUtilErr,
			OverSpendRatio:        overSpend,
			MultiplierCV:          cv,
			MultiplierHistory:     multipliers,
			SpendCurve:            spendCurve,
		})

		totalUtilError += dailyUtilErr
		totalOverSpend += overSpend
		totalCV += cv

		for _, m := range multipliers {
			if m != 0.0 {
				assert.GreaterOrEqual(t, m, 0.10,
					"Active multiplier should be >= PI min_multiplier (0.10) for campaign %d", cs.CampaignID)
			}
			assert.LessOrEqual(t, m, 2.0,
				"Multiplier should be <= 2.0 for campaign %d", cs.CampaignID)
		}

		switch cs.CampaignID {
		case 5:
			assert.LessOrEqual(t, dailyUtilErr, 0.20,
				"Premium campaign 5 daily utilization error should be <= 20%%")

		case 8:
			midRangeCount := 0
			for _, m := range multipliers {
				if m >= 0.5 && m <= 1.5 {
					midRangeCount++
				}
			}
			midRangePct := float64(midRangeCount) / float64(len(multipliers))
			t.Logf("Campaign 8 (Whale) mid-range [0.5–1.5] time: %.1f%%, CV: %.3f", midRangePct*100, cv)
			assert.Greater(t, spendDollars, 0.0,
				"Whale campaign 8 should have non-zero spend")
		}
	}

	n := float64(len(campaignReports))
	pacingReport := &evaluation.PacingReport{
		Campaigns:           campaignReports,
		MeanBudgetUtilError: totalUtilError / n,
		MeanOverSpendRatio:  totalOverSpend / n,
		MeanMultiplierCV:    totalCV / n,
	}

	t.Log(evaluation.PrintPacingReport(pacingReport))

	now := time.Now()
	runDir, err := evaluation.CreateRunDir(now)
	require.NoError(t, err)

	chartData := ChartData{
		Campaigns:    campaigns,
		Snapshots:    snapshots,
		NumIntervals: numIntervals,
		PacingEveryN: pacingEveryN,
		OutputDir:    runDir,
	}

	chartPaths, chartErr := GeneratePacingCharts(chartData)
	if chartErr != nil {
		t.Errorf("Failed to generate charts: %v", chartErr)
	} else {
		for _, p := range chartPaths {
			t.Logf("Chart: %s", p)
		}
	}

	report := evaluation.EvalReport{
		Timestamp: now,
		Duration:  "N/A",
		Pacing:    pacingReport,
	}
	if path, err := evaluation.WriteReport(report, runDir); err != nil {
		t.Logf("Warning: failed to write report: %v", err)
	} else {
		t.Logf("Report written to %s", path)
	}
}

func TestBudgetExhaustion(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping budget exhaustion test in short mode")
	}

	mr, err := miniredis.Run()
	require.NoError(t, err)
	defer mr.Close()

	redisURL := fmt.Sprintf("redis://%s", mr.Addr())

	testCmd := exec.Command("python3", "-c", "import redis; print('ok')")
	if err := testCmd.Run(); err != nil {
		t.Skipf("Python3 with redis package not available: %v", err)
	}

	cs := campaignSetup{CampaignID: 1, TotalBudget: 5, DailyBudget: 5, DurationDays: 7}
	seedCampaignState(t, mr, cs)

	bg := campaignSetup{CampaignID: 2, TotalBudget: 100000, DailyBudget: 50000, DurationDays: 7}
	seedCampaignState(t, mr, bg)

	mapping, _ := evalfixtures.LoadTaxonomyMapping()
	pages, _ := evalfixtures.GeneratePages()
	rng := rand.New(rand.NewSource(42))

	testAds := []models.AdVectorResult{
		{
			Ad: models.Ad{
				AdID: 1, CampaignID: 1, BidAmountCents: 500, PricingModel: models.CPM,
				Keywords: []models.KeywordTarget{{Keyword: "technology", RelevanceScore: 1.0}},
			},
			VectorScore: 0.5,
		},
		{
			Ad: models.Ad{
				AdID: 2, CampaignID: 2, BidAmountCents: 500, PricingModel: models.CPM,
				Keywords: []models.KeywordTarget{{Keyword: "technology", RelevanceScore: 1.0}},
			},
			VectorScore: 0.5,
		},
	}

	var multiplierHistory []float64
	campaign1Wins := 0
	totalAuctions := 0

	numIntervals := 50
	pacingEveryN := 2
	totalPacingCycles := numIntervals / pacingEveryN
	simDayStart := time.Now().UTC().Truncate(24 * time.Hour)
	secondsPerCycle := 86400.0 / float64(totalPacingCycles)
	pacingCycleIndex := 0

	for interval := 0; interval < numIntervals; interval++ {
		pacingMultipliers := map[int32]float64{
			1: readMultiplier(mr, 1),
			2: readMultiplier(mr, 2),
		}

		for r := 0; r < 10; r++ {
			page := pages[rng.Intn(len(pages))]
			candidates, _ := ads.ScoreAdsWithParams(testAds, page.PageContext, mapping, pacingMultipliers)
			if len(candidates) == 0 {
				continue
			}
			result := ads.RunSecondPriceAuction(candidates, 0.50)
			if !result.HasWinner {
				continue
			}
			totalAuctions++
			if result.Winner.Ad.CampaignID == 1 {
				campaign1Wins++
			}
			priceCents := int64(result.PricePaid * 100)
			if priceCents > 0 {
				incrementSpend(mr, result.Winner.Ad.CampaignID, priceCents)
			}
		}

		if (interval+1)%pacingEveryN == 0 {
			simTimeOffset := float64(simDayStart.Unix()) + float64(pacingCycleIndex)*secondsPerCycle
			pacingCycleIndex++

			m, err := runPythonPacing(t, redisURL, 1, simTimeOffset)
			if err != nil {
				t.Fatalf("Pacing failed: %v", err)
			}
			multiplierHistory = append(multiplierHistory, m)

			runPythonPacing(t, redisURL, 2, simTimeOffset)
		}
	}

	finalSpend := float64(readSpendCents(mr, 1)) / 100.0
	t.Logf("Campaign 1: spend=$%.2f / budget=$%.2f", finalSpend, cs.TotalBudget)
	t.Logf("Campaign 1 wins: %d / %d auctions", campaign1Wins, totalAuctions)
	t.Logf("Multiplier history: %v", fmtFloats(multiplierHistory))

	if len(multiplierHistory) > 2 {
		lastMult := multiplierHistory[len(multiplierHistory)-1]
		firstMult := multiplierHistory[0]
		t.Logf("Multiplier change: %.3f → %.3f", firstMult, lastMult)

		if finalSpend > cs.TotalBudget*0.3 {
			assert.Less(t, lastMult, firstMult+0.1,
				"Multiplier should trend downward as budget depletes")
		}
	}
}

func fmtFloats(fs []float64) string {
	parts := make([]string, len(fs))
	for i, f := range fs {
		parts[i] = fmt.Sprintf("%.3f", f)
	}
	return "[" + strings.Join(parts, ", ") + "]"
}
