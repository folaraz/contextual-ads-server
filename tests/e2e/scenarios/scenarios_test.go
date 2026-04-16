package scenarios

import (
	"context"
	"fmt"
	"testing"
	"time"

	"github.com/folaraz/contextual-ads-server/tests/client"
	"github.com/folaraz/contextual-ads-server/tests/config"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestAdServingBasicFlow(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping ad serving scenario in short mode")
	}

	cfg, err := config.LoadConfig("")
	require.NoError(t, err, "Failed to load config")

	scenario := NewAdServingScenario(cfg, true)

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	apiClient := client.NewClient(cfg)
	publishers, err := apiClient.ListPublishers()
	require.NoError(t, err, "Failed to list publishers")
	require.NotEmpty(t, publishers, "No publishers available")

	testCases := scenario.GenerateTestCases(publishers, 10)
	results := scenario.RunAllTestCases(ctx, testCases)

	assert.Len(t, results, 10, "Should have 10 results")

	var fills, noFills, errors int
	for _, r := range results {
		if r.Error != nil {
			errors++
		} else if r.HasFill {
			fills++
		} else {
			noFills++
		}
	}

	t.Logf("Results: %d fills, %d no-fills, %d errors", fills, noFills, errors)

	assert.Less(t, errors, 5, "Should have fewer than 5 errors")

	scenario.PrintSummary(results)
}

func TestAdServingWithSpecificKeywords(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping keyword scenario in short mode")
	}

	cfg, err := config.LoadConfig("")
	require.NoError(t, err, "Failed to load config")

	scenario := NewAdServingScenario(cfg, true)

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	apiClient := client.NewClient(cfg)
	publishers, err := apiClient.ListPublishers()
	require.NoError(t, err, "Failed to list publishers")
	require.NotEmpty(t, publishers, "No publishers available")

	publisher := publishers[0]

	ecommerceTC := AdServeTestCase{
		Name:        "E-commerce Keywords",
		PublisherID: fmt.Sprintf("%d", publisher.ID),
		PageURL:     fmt.Sprintf("https://%s/products/best-deals", publisher.Domain),
		Keywords:    []string{"shopping", "deals", "discount", "buy", "sale"},
		Title:       "Best Shopping Deals of 2026",
		Description: "Find the best deals and discounts on your favorite products",
		DeviceType:  "desktop",
		Language:    "en-US",
		ExpectFill:  true,
	}

	result := scenario.RunTestCase(ecommerceTC)
	assert.Nil(t, result.Error, "Should not have an error")
	t.Logf("E-commerce test: Fill=%v, Latency=%v", result.HasFill, result.Latency)

	techTC := AdServeTestCase{
		Name:        "Technology Keywords",
		PublisherID: fmt.Sprintf("%d", publisher.ID),
		PageURL:     fmt.Sprintf("https://%s/tech/software-review", publisher.Domain),
		Keywords:    []string{"technology", "software", "cloud", "AI", "innovation"},
		Title:       "Latest Software Technology Review",
		Description: "Comprehensive review of the latest software technologies",
		DeviceType:  "desktop",
		Language:    "en-US",
		ExpectFill:  true,
	}

	result = scenario.RunTestCase(techTC)
	assert.Nil(t, result.Error, "Should not have an error")
	t.Logf("Tech test: Fill=%v, Latency=%v", result.HasFill, result.Latency)

	_ = ctx
}

func TestAdServingDeviceVariations(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping device variation scenario in short mode")
	}

	cfg, err := config.LoadConfig("")
	require.NoError(t, err, "Failed to load config")

	scenario := NewAdServingScenario(cfg, true)

	apiClient := client.NewClient(cfg)
	publishers, err := apiClient.ListPublishers()
	require.NoError(t, err, "Failed to list publishers")
	require.NotEmpty(t, publishers, "No publishers available")

	publisher := publishers[0]

	devices := []string{"desktop", "mobile", "tablet"}

	for _, device := range devices {
		tc := AdServeTestCase{
			Name:        fmt.Sprintf("Device_%s", device),
			PublisherID: fmt.Sprintf("%d", publisher.ID),
			PageURL:     fmt.Sprintf("https://%s/article/test", publisher.Domain),
			Keywords:    []string{"technology", "news"},
			Title:       "Test Article",
			Description: "A test article description",
			DeviceType:  device,
			Language:    "en-US",
		}

		result := scenario.RunTestCase(tc)
		assert.Nil(t, result.Error, "Should not have an error for device %s", device)
		t.Logf("%s: Fill=%v, Latency=%v", device, result.HasFill, result.Latency)
	}
}

func TestAdServingLatencyBenchmark(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping latency benchmark in short mode")
	}

	cfg, err := config.LoadConfig("")
	require.NoError(t, err, "Failed to load config")

	scenario := NewAdServingScenario(cfg, false)

	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()

	apiClient := client.NewClient(cfg)
	publishers, err := apiClient.ListPublishers()
	require.NoError(t, err, "Failed to list publishers")
	require.NotEmpty(t, publishers, "No publishers available")

	testCases := scenario.GenerateTestCases(publishers, 50)
	results := scenario.RunAllTestCases(ctx, testCases)

	var latencies []time.Duration
	for _, r := range results {
		if r.Error == nil {
			latencies = append(latencies, r.Latency)
		}
	}

	if len(latencies) == 0 {
		t.Skip("No successful requests to measure latency")
	}

	sortDurations(latencies)

	p50 := latencies[len(latencies)*50/100]
	p95 := latencies[len(latencies)*95/100]
	p99 := latencies[len(latencies)*99/100]

	t.Logf("Latency percentiles:")
	t.Logf("  p50: %v", p50)
	t.Logf("  p95: %v", p95)
	t.Logf("  p99: %v", p99)

	assert.Less(t, p99.Milliseconds(), int64(500), "p99 latency should be under 500ms")
}

func TestEventTrackingFullLifecycle(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping full lifecycle test in short mode")
	}

	cfg, err := config.LoadConfig("")
	require.NoError(t, err, "Failed to load config")

	scenario := NewEventTrackingScenario(cfg, true)

	apiClient := client.NewClient(cfg)
	publishers, err := apiClient.ListPublishers()
	require.NoError(t, err, "Failed to list publishers")
	require.NotEmpty(t, publishers, "No publishers available")

	publisher := publishers[0]

	domain := publisher.Domain
	if domain == "" {
		domain = fmt.Sprintf("publisher-%d.com", publisher.ID)
	}

	lifecycle := &FullEventLifecycle{
		PublisherID: fmt.Sprintf("%d", publisher.ID),
		PageURL:     fmt.Sprintf("https://%s/test-article", domain),
		Keywords:    []string{"shopping", "deals", "products"},
		DeviceType:  "desktop",
	}

	err = scenario.RunFullLifecycle(lifecycle)
	assert.NoError(t, err, "Lifecycle test should complete without error")

	result := lifecycle.Result
	if result.AdServeSuccess {
		t.Logf("Ad served: ID=%d, Auction=%s", result.AdID, result.AuctionID)
		t.Logf("Ad serve latency: %v", result.AdServeLatency)

		if result.ImpressionSuccess {
			t.Logf("Impression tracked: latency=%v", result.ImpressionLatency)
		}

		if result.ClickSuccess {
			t.Logf("Click tracked: latency=%v", result.ClickLatency)
		}
	} else {
		t.Log("No ad fill for this request")
	}
}

func TestEventTrackingBatch(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping batch event test in short mode")
	}

	cfg, err := config.LoadConfig("")
	require.NoError(t, err, "Failed to load config")

	scenario := NewEventTrackingScenario(cfg, true)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	apiClient := client.NewClient(cfg)
	publishers, err := apiClient.ListPublishers()
	require.NoError(t, err, "Failed to list publishers")
	require.NotEmpty(t, publishers, "No publishers available")

	batchTest := &BatchEventTest{
		Publishers: publishers,
		NumTests:   20,
	}

	err = scenario.RunBatchTest(ctx, batchTest)
	require.NoError(t, err, "Batch test should complete")

	scenario.PrintBatchSummary(batchTest.Results)

	var adServes, impressions, clicks int
	for _, r := range batchTest.Results {
		if r.AdServeSuccess {
			adServes++
		}
		if r.ImpressionSuccess {
			impressions++
		}
		if r.ClickSuccess {
			clicks++
		}
	}

	t.Logf("Batch results: %d ad serves, %d impressions, %d clicks", adServes, impressions, clicks)

	if adServes > 0 {
		impressionRate := float64(impressions) / float64(adServes) * 100
		t.Logf("Impression success rate: %.1f%%", impressionRate)
	}
}

func TestImpressionTrackingOnly(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping impression tracking test in short mode")
	}

	cfg, err := config.LoadConfig("")
	require.NoError(t, err, "Failed to load config")

	apiClient := client.NewClient(cfg)

	publishers, err := apiClient.ListPublishers()
	require.NoError(t, err, "Failed to list publishers")
	require.NotEmpty(t, publishers, "No publishers available")

	publisher := publishers[0]

	adReq := client.AdServeRequest{
		PublisherID: fmt.Sprintf("%d", publisher.ID),
		Context: client.AdContext{
			URL:         fmt.Sprintf("https://%s/test", publisher.Domain),
			Keywords:    []string{"technology", "software"},
			Title:       "Test Page",
			Description: "Test description",
		},
		Device: client.DeviceInfo{
			Type:     "desktop",
			Language: "en-US",
		},
	}

	adResp, err := apiClient.ServeAd(adReq)
	if err != nil {
		t.Skipf("Could not get an ad to test impressions: %v", err)
	}

	if adResp.ImpressionURL == "" {
		t.Skip("No impression URL in response")
	}

	t.Logf("Got ad with impression URL")

	for i := 0; i < 3; i++ {
		err = apiClient.TrackImpression(adResp.ImpressionURL)
		assert.NoError(t, err, "Impression %d should be tracked", i+1)
		t.Logf("Impression %d tracked", i+1)
		time.Sleep(100 * time.Millisecond)
	}
}

func sortDurations(d []time.Duration) {
	for i := 0; i < len(d)-1; i++ {
		for j := i + 1; j < len(d); j++ {
			if d[i] > d[j] {
				d[i], d[j] = d[j], d[i]
			}
		}
	}
}
