package ads

import (
	"context"
	"fmt"
	"strconv"
	"time"

	"github.com/folaraz/contextual-ads-server/internal/observability"
	goredis "github.com/redis/go-redis/v9"
)

type CampaignState struct {
	CampaignID         string  `redis:"campaign_id"`
	AdvertiserID       string  `redis:"advertiser_id"`
	TotalBudget        string  `redis:"total_budget"`
	DailyBudget        string  `redis:"daily_budget"`
	StartTime          int64   `redis:"start_time"`
	EndTime            int64   `redis:"end_time"`
	Status             string  `redis:"status"`
	CurrentMultiplier  float64 `redis:"current_multiplier"`
	PreviousMultiplier float64 `redis:"previous_multiplier"`
	CumulativeErrors   float64 `redis:"cumulative_errors"`
	CreatedAt          int64   `redis:"created_at"`
	UpdatedAt          int64   `redis:"updated_at"`
}

type PacingService struct {
	RedisClient *goredis.Client
}

func NewPacingService(redisClient *goredis.Client) *PacingService {
	return &PacingService{
		RedisClient: redisClient,
	}
}

func CampaignStateKey(campaignID string) string {
	return fmt.Sprintf("campaign:%s:state", campaignID)
}

func (p *PacingService) GetPacingMultiplier(campaignID int32) float64 {
	campaignIDStr := fmt.Sprintf("%d", campaignID)
	state, err := p.GetCampaignState(campaignIDStr)
	if err != nil {
		return 1.0
	}
	if state == nil {
		return 1.0
	}
	return state.CurrentMultiplier
}

func (p *PacingService) GetCampaignState(campaignID string) (*CampaignState, error) {
	ctx := context.Background()
	key := CampaignStateKey(campaignID)

	start := time.Now()
	result, err := p.RedisClient.HGetAll(ctx, key).Result()
	duration := time.Since(start)

	if err != nil {
		observability.RecordCacheOperation(ctx, "pacing_state", "get", false, duration)
		return nil, fmt.Errorf("failed to get campaign state: %w", err)
	}

	found := len(result) > 0
	observability.RecordCacheOperation(ctx, "pacing_state", "get", found, duration)

	if !found {
		return nil, nil
	}

	return parseCampaignState(result), nil
}

func parseCampaignState(result map[string]string) *CampaignState {
	if len(result) == 0 {
		return nil
	}

	state := &CampaignState{
		CampaignID:        result["campaign_id"],
		AdvertiserID:      result["advertiser_id"],
		TotalBudget:       result["total_budget"],
		DailyBudget:       result["daily_budget"],
		Status:            result["status"],
		CurrentMultiplier: 1.0,
	}

	if v, err := strconv.ParseInt(result["start_time"], 10, 64); err == nil {
		state.StartTime = v
	}
	if v, err := strconv.ParseInt(result["end_time"], 10, 64); err == nil {
		state.EndTime = v
	}
	if v, err := strconv.ParseFloat(result["current_multiplier"], 64); err == nil {
		state.CurrentMultiplier = v
	}
	if v, err := strconv.ParseFloat(result["previous_multiplier"], 64); err == nil {
		state.PreviousMultiplier = v
	}
	if v, err := strconv.ParseFloat(result["cumulative_errors"], 64); err == nil {
		state.CumulativeErrors = v
	}
	if v, err := strconv.ParseInt(result["created_at"], 10, 64); err == nil {
		state.CreatedAt = v
	}
	if v, err := strconv.ParseInt(result["updated_at"], 10, 64); err == nil {
		state.UpdatedAt = v
	}

	return state
}

func CampaignDailyKey(campaignID string) string {
	today := time.Now().UTC().Format("2006-01-02")
	return fmt.Sprintf("campaign:%s:daily:%s", campaignID, today)
}

func CampaignMetricsKey(campaignID string) string {
	return fmt.Sprintf("campaign:%s:metrics", campaignID)
}

func (p *PacingService) GetPacingMultipliers(campaignIDs []int32) map[int32]float64 {
	result := make(map[int32]float64, len(campaignIDs))
	if len(campaignIDs) == 0 {
		return result
	}

	seen := make(map[int32]bool, len(campaignIDs))
	uniqueIDs := make([]int32, 0, len(campaignIDs))
	for _, id := range campaignIDs {
		if !seen[id] {
			seen[id] = true
			uniqueIDs = append(uniqueIDs, id)
		}
	}

	ctx := context.Background()
	start := time.Now()
	pipe := p.RedisClient.Pipeline()

	stateCmds := make(map[int32]*goredis.MapStringStringCmd, len(uniqueIDs))
	metricsCmds := make(map[int32]*goredis.MapStringStringCmd, len(uniqueIDs))
	dailyCmds := make(map[int32]*goredis.MapStringStringCmd, len(uniqueIDs))
	for _, id := range uniqueIDs {
		idStr := fmt.Sprintf("%d", id)
		stateCmds[id] = pipe.HGetAll(ctx, CampaignStateKey(idStr))
		metricsCmds[id] = pipe.HGetAll(ctx, CampaignMetricsKey(idStr))
		dailyCmds[id] = pipe.HGetAll(ctx, CampaignDailyKey(idStr))
	}

	_, err := pipe.Exec(ctx)
	duration := time.Since(start)

	if err != nil {
		observability.RecordCacheOperation(ctx, "pacing_state_batch", "get", false, duration)
		for _, id := range uniqueIDs {
			result[id] = 1.0
		}
		return result
	}

	observability.RecordCacheOperation(ctx, "pacing_state_batch", "get", true, duration)

	for _, id := range uniqueIDs {
		stateData, err := stateCmds[id].Result()
		if err != nil || len(stateData) == 0 {
			result[id] = 1.0
			continue
		}
		state := parseCampaignState(stateData)
		if state == nil {
			result[id] = 1.0
			continue
		}

		totalBudgetCents := parseCentsFromDollars(state.TotalBudget)
		if totalBudgetCents > 0 {
			metricsData, _ := metricsCmds[id].Result()
			totalSpendCents := parseRedisInt64(metricsData, "spend_cents")
			if totalSpendCents >= totalBudgetCents {
				result[id] = 0.0
				observability.Info(ctx, "Hard cap: total budget exhausted",
					"campaign_id", id,
					"total_spend_cents", totalSpendCents,
					"total_budget_cents", totalBudgetCents,
				)
				continue
			}
		}

		dailyBudgetCents := parseCentsFromDollars(state.DailyBudget)
		if dailyBudgetCents > 0 {
			dailyData, _ := dailyCmds[id].Result()
			dailySpendCents := parseRedisInt64(dailyData, "spend_cents")
			if dailySpendCents >= dailyBudgetCents {
				result[id] = 0.0
				observability.Info(ctx, "Hard cap: daily budget exhausted",
					"campaign_id", id,
					"daily_spend_cents", dailySpendCents,
					"daily_budget_cents", dailyBudgetCents,
				)
				continue
			}
		}

		result[id] = state.CurrentMultiplier
	}

	return result
}

func parseCentsFromDollars(dollars string) int64 {
	if dollars == "" {
		return 0
	}
	val, err := strconv.ParseFloat(dollars, 64)
	if err != nil {
		return 0
	}
	return int64(val * 100)
}

func parseRedisInt64(data map[string]string, field string) int64 {
	if data == nil {
		return 0
	}
	v, ok := data[field]
	if !ok {
		return 0
	}
	n, err := strconv.ParseInt(v, 10, 64)
	if err != nil {
		return 0
	}
	return n
}
