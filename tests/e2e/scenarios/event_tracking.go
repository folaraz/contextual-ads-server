package scenarios

import (
	"context"
	"fmt"
	"strings"
	"time"

	"github.com/folaraz/contextual-ads-server/tests/client"
	"github.com/folaraz/contextual-ads-server/tests/config"
	"github.com/folaraz/contextual-ads-server/tests/helpers"
)

type EventTrackingScenario struct {
	client  *client.Client
	config  *config.Config
	gen     *helpers.Generator
	verbose bool
}

func NewEventTrackingScenario(cfg *config.Config, verbose bool) *EventTrackingScenario {
	c := client.NewClient(cfg)
	c.SetVerbose(verbose)

	return &EventTrackingScenario{
		client:  c,
		config:  cfg,
		gen:     helpers.NewGenerator(),
		verbose: verbose,
	}
}

type EventTestResult struct {
	AdServeLatency    time.Duration
	ImpressionLatency time.Duration
	ClickLatency      time.Duration
	AdServeSuccess    bool
	ImpressionSuccess bool
	ClickSuccess      bool
	AdID              int32
	AuctionID         string
	ImpressionURL     string
	ClickURL          string
	Error             error
}

type FullEventLifecycle struct {
	PublisherID string
	PageURL     string
	Keywords    []string
	DeviceType  string

	Result *EventTestResult
}

func (s *EventTrackingScenario) RunFullLifecycle(lc *FullEventLifecycle) error {
	result := &EventTestResult{}
	lc.Result = result

	s.log("Starting full event lifecycle test")
	s.log("  Publisher: %s", lc.PublisherID)
	s.log("  Page URL: %s", lc.PageURL)
	s.log("  Device: %s", lc.DeviceType)

	s.log("\nStep 1: Requesting ad...")
	adReq := client.AdServeRequest{
		PublisherID: lc.PublisherID,
		Context: client.AdContext{
			URL:         lc.PageURL,
			Keywords:    lc.Keywords,
			Title:       "Test Article",
			Description: "A test article for event tracking validation",
		},
		Device: client.DeviceInfo{
			Type:      lc.DeviceType,
			UserAgent: s.gen.RandomUserAgent(lc.DeviceType),
			Language:  "en-US",
		},
		Meta: client.RequestMeta{
			Timestamp: time.Now().Unix(),
		},
	}

	start := time.Now()
	adResp, err := s.client.ServeAd(adReq)
	result.AdServeLatency = time.Since(start)

	if err != nil {
		if strings.Contains(err.Error(), "204") || strings.Contains(err.Error(), "no content") {
			s.log("  No ad returned (no fill)")
			result.AdServeSuccess = false
			return nil
		}
		result.Error = fmt.Errorf("ad serve failed: %w", err)
		return result.Error
	}

	result.AdServeSuccess = true
	result.ImpressionURL = adResp.ImpressionURL
	result.ClickURL = adResp.ClickURL
	result.AuctionID = adResp.AuctionID
	result.AdID = adResp.AdID

	s.log("  Ad served successfully")
	s.log("  Ad ID: %d", result.AdID)
	s.log("  Auction ID: %s", result.AuctionID)
	s.log("  Latency: %v", result.AdServeLatency)

	if result.ImpressionURL != "" {
		s.log("\nStep 2: Firing impression...")
		start = time.Now()
		err = s.client.TrackImpression(result.ImpressionURL)
		result.ImpressionLatency = time.Since(start)

		if err != nil {
			s.log("  Impression tracking failed: %v", err)
			result.ImpressionSuccess = false
		} else {
			s.log("  Impression tracked successfully")
			s.log("  Latency: %v", result.ImpressionLatency)
			result.ImpressionSuccess = true
		}
	} else {
		s.log("\nStep 2: Skipping impression (no URL)")
	}

	if result.ClickURL != "" {
		s.log("\nStep 3: Firing click...")
		start = time.Now()
		err = s.client.TrackClick(result.ClickURL)
		result.ClickLatency = time.Since(start)

		if err != nil {
			s.log("  Click tracking failed: %v", err)
			result.ClickSuccess = false
		} else {
			s.log("  Click tracked successfully")
			s.log("  Latency: %v", result.ClickLatency)
			result.ClickSuccess = true
		}
	} else {
		s.log("\nStep 3: Skipping click (no URL - may be CPM ad)")
	}

	return nil
}

type BatchEventTest struct {
	Publishers []client.Publisher
	NumTests   int

	Results []*EventTestResult
}

func (s *EventTrackingScenario) RunBatchTest(ctx context.Context, bt *BatchEventTest) error {
	s.log("Starting batch event test with %d iterations", bt.NumTests)

	bt.Results = make([]*EventTestResult, 0, bt.NumTests)
	devices := []string{"desktop", "mobile", "tablet"}

	for i := 0; i < bt.NumTests; i++ {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		publisher := helpers.RandomChoice(s.gen, bt.Publishers)
		device := helpers.RandomChoice(s.gen, devices)

		domain := publisher.Domain
		if domain == "" {
			domain = fmt.Sprintf("publisher-%d.com", publisher.ID)
		}

		lc := &FullEventLifecycle{
			PublisherID: fmt.Sprintf("%d", publisher.ID),
			PageURL:     fmt.Sprintf("https://%s/article/%s", domain, s.gen.RandomSlug(3)),
			Keywords:    s.randomKeywords(),
			DeviceType:  device,
		}

		s.log("\n--- Test %d/%d ---", i+1, bt.NumTests)
		err := s.RunFullLifecycle(lc)
		if err != nil {
			s.log("Test %d failed: %v", i+1, err)
		}

		bt.Results = append(bt.Results, lc.Result)

		time.Sleep(100 * time.Millisecond)
	}

	return nil
}

func (s *EventTrackingScenario) PrintBatchSummary(results []*EventTestResult) {
	fmt.Println("\n" + strings.Repeat("=", 60))
	fmt.Println("EVENT TRACKING BATCH TEST - SUMMARY")
	fmt.Println(strings.Repeat("=", 60))

	var total, adServeSuccess, impressionSuccess, clickSuccess int
	var totalAdLatency, totalImpLatency, totalClickLatency time.Duration

	for _, r := range results {
		total++
		if r.AdServeSuccess {
			adServeSuccess++
			totalAdLatency += r.AdServeLatency
		}
		if r.ImpressionSuccess {
			impressionSuccess++
			totalImpLatency += r.ImpressionLatency
		}
		if r.ClickSuccess {
			clickSuccess++
			totalClickLatency += r.ClickLatency
		}
	}

	fmt.Printf("\nTotal Tests: %d\n", total)

	fmt.Println("\nAd Serving:")
	fmt.Printf("  Success: %d (%.1f%%)\n", adServeSuccess, pct(adServeSuccess, total))
	if adServeSuccess > 0 {
		fmt.Printf("  Avg Latency: %v\n", totalAdLatency/time.Duration(adServeSuccess))
	}

	fmt.Println("\nImpressions:")
	fmt.Printf("  Success: %d (%.1f%% of fills)\n", impressionSuccess, pct(impressionSuccess, adServeSuccess))
	if impressionSuccess > 0 {
		fmt.Printf("  Avg Latency: %v\n", totalImpLatency/time.Duration(impressionSuccess))
	}

	fmt.Println("\nClicks:")
	fmt.Printf("  Success: %d (%.1f%% of fills)\n", clickSuccess, pct(clickSuccess, adServeSuccess))
	if clickSuccess > 0 {
		fmt.Printf("  Avg Latency: %v\n", totalClickLatency/time.Duration(clickSuccess))
	}

	if impressionSuccess > 0 {
		ctr := float64(clickSuccess) / float64(impressionSuccess) * 100
		fmt.Printf("\nCTR: %.2f%%\n", ctr)
	}

	fmt.Println(strings.Repeat("=", 60))
}

func (s *EventTrackingScenario) randomKeywords() []string {
	keywords := [][]string{
		{"technology", "software", "cloud"},
		{"shopping", "deals", "discount"},
		{"travel", "vacation", "hotels"},
		{"finance", "investing", "crypto"},
		{"health", "fitness", "wellness"},
	}
	return helpers.RandomChoice(s.gen, keywords)
}

func (s *EventTrackingScenario) log(format string, args ...interface{}) {
	if s.verbose {
		fmt.Printf(format+"\n", args...)
	}
}

func pct(part, total int) float64 {
	if total == 0 {
		return 0
	}
	return float64(part) / float64(total) * 100
}
