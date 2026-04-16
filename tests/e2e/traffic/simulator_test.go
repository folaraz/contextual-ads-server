package traffic

import (
	"context"
	"testing"
	"time"

	"github.com/folaraz/contextual-ads-server/tests/config"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestBasicTrafficSimulation(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping traffic simulation in short mode")
	}

	cfg, err := config.LoadConfig("")
	require.NoError(t, err, "Failed to load config")

	simulator := NewTrafficSimulator(cfg,
		WithVerboseSimulator(true),
	)

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	trafficCfg := TrafficConfig{
		NumRequests:    20,
		Concurrency:    5,
		RateLimit:      0,
		ImpressionRate: 0.8,
		ClickRate:      0.05,
		DeviceDistribution: map[string]float64{
			"desktop": 0.5,
			"mobile":  0.4,
			"tablet":  0.1,
		},
	}

	result, err := simulator.Run(ctx, trafficCfg)
	require.NoError(t, err, "Traffic simulation should complete without error")

	assert.Equal(t, int64(trafficCfg.NumRequests), result.Stats.TotalRequests,
		"Should have made the requested number of requests")

	totalProcessed := result.Stats.SuccessfulRequests + result.Stats.NoFillRequests
	assert.Greater(t, totalProcessed, int64(0),
		"At least some requests should be processed")

	if result.Stats.SuccessfulRequests > 0 {
		assert.Greater(t, result.Stats.TotalImpressions, int64(0),
			"Should have some impressions for filled requests")
	}
}

func TestHighVolumeTrafficSimulation(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping high volume traffic simulation in short mode")
	}

	cfg, err := config.LoadConfig("")
	require.NoError(t, err, "Failed to load config")

	simulator := NewTrafficSimulator(cfg,
		WithVerboseSimulator(true),
	)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	trafficCfg := TrafficConfig{
		NumRequests:    100,
		Concurrency:    20,
		RateLimit:      50,
		ImpressionRate: 0.85,
		ClickRate:      0.03,
		DeviceDistribution: map[string]float64{
			"desktop": 0.45,
			"mobile":  0.45,
			"tablet":  0.10,
		},
	}

	result, err := simulator.Run(ctx, trafficCfg)
	require.NoError(t, err, "Traffic simulation should complete without error")

	assert.Equal(t, int64(trafficCfg.NumRequests), result.Stats.TotalRequests)

	errorRate := float64(result.Stats.FailedRequests) / float64(result.Stats.TotalRequests)
	assert.Less(t, errorRate, 0.05, "Error rate should be less than 5%%")

	if result.Stats.SuccessfulRequests > 0 {
		avgLatency := float64(result.Stats.TotalLatencyMs) / float64(result.Stats.TotalRequests)
		assert.Less(t, avgLatency, 500.0, "Average latency should be less than 500ms")

		assert.Less(t, result.Stats.MaxLatencyMs, int64(2000),
			"Max latency should be less than 2000ms")
	}
}

func TestBurstTrafficSimulation(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping burst traffic simulation in short mode")
	}

	cfg, err := config.LoadConfig("")
	require.NoError(t, err, "Failed to load config")

	simulator := NewTrafficSimulator(cfg,
		WithVerboseSimulator(true),
	)

	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()

	trafficCfg := TrafficConfig{
		NumRequests:    50,
		Concurrency:    50,
		RateLimit:      0,
		ImpressionRate: 0.9,
		ClickRate:      0.02,
		DeviceDistribution: map[string]float64{
			"desktop": 0.33,
			"mobile":  0.34,
			"tablet":  0.33,
		},
	}

	result, err := simulator.Run(ctx, trafficCfg)
	require.NoError(t, err, "Burst traffic simulation should complete")

	assert.Equal(t, int64(trafficCfg.NumRequests), result.Stats.TotalRequests)

	errorRate := float64(result.Stats.FailedRequests) / float64(result.Stats.TotalRequests)
	assert.Less(t, errorRate, 0.10, "Error rate should be less than 10%% under burst")

	assert.Less(t, result.Duration.Seconds(), 30.0,
		"Burst simulation should complete within 30 seconds")
}

func TestTrafficWithCustomKeywords(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping custom keyword traffic test in short mode")
	}

	cfg, err := config.LoadConfig("")
	require.NoError(t, err, "Failed to load config")

	simulator := NewTrafficSimulator(cfg,
		WithVerboseSimulator(true),
	)

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	trafficCfg := TrafficConfig{
		NumRequests:    30,
		Concurrency:    10,
		RateLimit:      0,
		ImpressionRate: 0.9,
		ClickRate:      0.05,
		DeviceDistribution: map[string]float64{
			"desktop": 0.6,
			"mobile":  0.3,
			"tablet":  0.1,
		},
		Keywords: []string{
			"shopping", "deals", "discount", "sale", "buy",
			"online shopping", "best price", "free shipping",
		},
	}

	result, err := simulator.Run(ctx, trafficCfg)
	require.NoError(t, err, "Custom keyword traffic simulation should complete")

	t.Logf("Fill rate with matching keywords: %.1f%%",
		float64(result.Stats.SuccessfulRequests)/float64(result.Stats.TotalRequests)*100)
}

func TestMobileOnlyTraffic(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping mobile-only traffic test in short mode")
	}

	cfg, err := config.LoadConfig("")
	require.NoError(t, err, "Failed to load config")

	simulator := NewTrafficSimulator(cfg,
		WithVerboseSimulator(true),
	)

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	trafficCfg := TrafficConfig{
		NumRequests:    20,
		Concurrency:    5,
		RateLimit:      0,
		ImpressionRate: 0.8,
		ClickRate:      0.05,
		DeviceDistribution: map[string]float64{
			"mobile": 1.0,
		},
	}

	result, err := simulator.Run(ctx, trafficCfg)
	require.NoError(t, err, "Mobile-only traffic simulation should complete")

	assert.Equal(t, int64(trafficCfg.NumRequests), result.Stats.TotalRequests)
}
