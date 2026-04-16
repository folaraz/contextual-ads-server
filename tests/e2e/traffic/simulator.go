package traffic

import (
	"context"
	"fmt"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/folaraz/contextual-ads-server/tests/client"
	"github.com/folaraz/contextual-ads-server/tests/config"
	"github.com/folaraz/contextual-ads-server/tests/helpers"
)

type TrafficSimulator struct {
	client  *client.Client
	config  *config.Config
	gen     *helpers.Generator
	verbose bool

	publishers []client.Publisher

	stats *TrafficStats
}

type TrafficStats struct {
	mu sync.RWMutex

	TotalRequests      int64
	SuccessfulRequests int64
	NoFillRequests     int64
	FailedRequests     int64
	TotalLatencyMs     int64
	MinLatencyMs       int64
	MaxLatencyMs       int64

	TotalImpressions      int64
	SuccessfulImpressions int64
	FailedImpressions     int64

	TotalClicks      int64
	SuccessfulClicks int64
	FailedClicks     int64

	PublisherStats map[string]*PublisherStats

	CountryStats map[string]*CountryStats

	CPMImpressions int64
	CPCClicks      int64

	StartTime time.Time
	EndTime   time.Time
}

type PublisherStats struct {
	Requests    int64
	Fills       int64
	NoFills     int64
	Impressions int64
	Clicks      int64
}

type CountryStats struct {
	Requests int64
	Fills    int64
	NoFills  int64
}

type SimulatorOption func(*TrafficSimulator)

func WithVerboseSimulator(verbose bool) SimulatorOption {
	return func(s *TrafficSimulator) {
		s.verbose = verbose
	}
}

func NewTrafficSimulator(cfg *config.Config, opts ...SimulatorOption) *TrafficSimulator {
	s := &TrafficSimulator{
		client:     client.NewClient(cfg),
		config:     cfg,
		gen:        helpers.NewGenerator(),
		publishers: make([]client.Publisher, 0),
		stats: &TrafficStats{
			PublisherStats: make(map[string]*PublisherStats),
			CountryStats:   make(map[string]*CountryStats),
			MinLatencyMs:   int64(^uint64(0) >> 1),
		},
	}

	for _, opt := range opts {
		opt(s)
	}

	s.client.SetVerbose(s.verbose)
	return s
}

type TrafficConfig struct {
	NumRequests int

	Duration time.Duration

	Concurrency int

	RateLimit int

	ImpressionRate float64

	ClickRate float64

	DeviceDistribution map[string]float64

	CountryDistribution map[string]float64

	PageURLs []string

	Keywords []string
}

type TrafficResult struct {
	Stats    *TrafficStats
	Errors   []error
	Duration time.Duration
}

func (s *TrafficSimulator) Run(ctx context.Context, cfg TrafficConfig) (*TrafficResult, error) {
	if len(s.publishers) == 0 {
		pubs, err := s.client.ListPublishers()
		if err != nil {
			return nil, fmt.Errorf("no publishers available and failed to fetch: %w", err)
		}
		s.publishers = pubs
	}

	if len(s.publishers) == 0 {
		return nil, fmt.Errorf("no publishers available for traffic simulation")
	}

	s.log("Starting traffic simulation...")
	if cfg.Duration > 0 {
		s.log("  Mode: duration-based (%v)", cfg.Duration)
	} else {
		s.log("  Requests: %d", cfg.NumRequests)
	}
	s.log("  Concurrency: %d", cfg.Concurrency)
	s.log("  Publishers: %d", len(s.publishers))
	s.log("  Impression Rate: %.1f%%", cfg.ImpressionRate*100)
	s.log("  Click Rate: %.1f%%", cfg.ClickRate*100)
	if len(cfg.CountryDistribution) > 0 {
		s.log("  Countries: %v", cfg.CountryDistribution)
	}

	s.stats.StartTime = time.Now()

	var errorsMu sync.Mutex
	var errors []error

	var wg sync.WaitGroup

	if cfg.Duration > 0 {
		for i := 0; i < cfg.Concurrency; i++ {
			wg.Add(1)
			go func(workerID int) {
				defer wg.Done()
				for {
					select {
					case <-ctx.Done():
						return
					default:
					}

					err := s.processRequest(cfg)
					if err != nil {
						errorsMu.Lock()
						errors = append(errors, err)
						errorsMu.Unlock()
					}

					if cfg.RateLimit > 0 && cfg.Concurrency > 0 {
						time.Sleep(time.Second / time.Duration(cfg.RateLimit/cfg.Concurrency+1))
					}
				}
			}(i)
		}
	} else {
		requestCh := make(chan int, cfg.NumRequests)
		for i := 0; i < cfg.NumRequests; i++ {
			requestCh <- i
		}
		close(requestCh)

		for i := 0; i < cfg.Concurrency; i++ {
			wg.Add(1)
			go func(workerID int) {
				defer wg.Done()
				for range requestCh {
					select {
					case <-ctx.Done():
						return
					default:
					}

					err := s.processRequest(cfg)
					if err != nil {
						errorsMu.Lock()
						errors = append(errors, err)
						errorsMu.Unlock()
					}

					if cfg.RateLimit > 0 && cfg.Concurrency > 0 {
						time.Sleep(time.Second / time.Duration(cfg.RateLimit/cfg.Concurrency+1))
					}
				}
			}(i)
		}
	}

	wg.Wait()
	s.stats.EndTime = time.Now()

	result := &TrafficResult{
		Stats:    s.stats,
		Errors:   errors,
		Duration: s.stats.EndTime.Sub(s.stats.StartTime),
	}

	s.printSummary(result)
	return result, nil
}

func (s *TrafficSimulator) processRequest(cfg TrafficConfig) error {
	publisher := helpers.RandomChoice(s.gen, s.publishers)
	publisherID := fmt.Sprintf("%d", publisher.ID)

	pageContext := s.generatePageContext(cfg, publisher)

	deviceType := s.selectDeviceType(cfg.DeviceDistribution)
	userAgent := s.gen.RandomUserAgent(deviceType)

	country := s.selectCountry(cfg.CountryDistribution)

	adRequest := client.AdServeRequest{
		PublisherID: publisherID,
		Context: client.AdContext{
			URL:         pageContext.URL,
			Keywords:    pageContext.Keywords,
			Title:       pageContext.Title,
			Description: pageContext.Description,
		},
		Device: client.DeviceInfo{
			Type:      deviceType,
			UserAgent: userAgent,
			Language:  "en-US",
		},
		Meta: client.RequestMeta{
			Timestamp: time.Now().Unix(),
		},
	}

	atomic.AddInt64(&s.stats.TotalRequests, 1)
	s.updatePublisherStats(publisherID, func(ps *PublisherStats) {
		ps.Requests++
	})
	s.updateCountryStats(country, func(cs *CountryStats) {
		cs.Requests++
	})

	start := time.Now()
	var opts []client.RequestOption
	if country != "" {
		opts = append(opts, client.WithHeader("X-Geo-Country", country))
	}
	adResp, err := s.client.ServeAd(adRequest, opts...)
	latencyMs := time.Since(start).Milliseconds()

	atomic.AddInt64(&s.stats.TotalLatencyMs, latencyMs)
	s.updateMinMax(latencyMs)

	if err != nil {
		if strings.Contains(err.Error(), "204") || strings.Contains(err.Error(), "no content") {
			atomic.AddInt64(&s.stats.NoFillRequests, 1)
			s.updatePublisherStats(publisherID, func(ps *PublisherStats) {
				ps.NoFills++
			})
			s.updateCountryStats(country, func(cs *CountryStats) {
				cs.NoFills++
			})
			return nil
		}

		atomic.AddInt64(&s.stats.FailedRequests, 1)
		return fmt.Errorf("ad serve failed for publisher %s: %w", publisherID, err)
	}

	atomic.AddInt64(&s.stats.SuccessfulRequests, 1)
	s.updatePublisherStats(publisherID, func(ps *PublisherStats) {
		ps.Fills++
	})
	s.updateCountryStats(country, func(cs *CountryStats) {
		cs.Fills++
	})

	impressionThreshold := s.gen.RandomFloat(cfg.ImpressionRate*0.7, cfg.ImpressionRate)
	if s.gen.RandomFloat(0, 1) <= impressionThreshold && adResp.ImpressionURL != "" {
		err = s.simulateImpression(adResp, publisherID)
		if err != nil {
			s.log("Impression tracking failed: %v", err)
		}

		clickThreshold := s.gen.RandomFloat(cfg.ClickRate*0.3, cfg.ClickRate)
		if s.gen.RandomFloat(0, 1) <= clickThreshold && adResp.ClickURL != "" {
			err = s.simulateClick(adResp, publisherID)
			if err != nil {
				s.log("Click tracking failed: %v", err)
			}
		}
	}

	return nil
}

type PageContext struct {
	URL         string
	Title       string
	Description string
	Keywords    []string
}

func (s *TrafficSimulator) generatePageContext(cfg TrafficConfig, publisher client.Publisher) PageContext {
	var pageURL string
	if len(cfg.PageURLs) > 0 {
		pageURL = helpers.RandomChoice(s.gen, cfg.PageURLs)
	} else {
		pageURL = s.generatePageURL(publisher)
	}

	var keywords []string
	if len(cfg.Keywords) > 0 {
		keywords = helpers.RandomSample(s.gen, cfg.Keywords, s.gen.RandomInt(2, 5))
	} else {
		keywords = s.generateKeywords()
	}

	title := s.generatePageTitle(keywords)
	description := s.generatePageDescription(keywords)

	return PageContext{
		URL:         pageURL,
		Title:       title,
		Description: description,
		Keywords:    keywords,
	}
}

func (s *TrafficSimulator) generatePageURL(publisher client.Publisher) string {
	paths := []string{
		"/articles/%s",
		"/news/%s",
		"/blog/%s",
		"/post/%s",
		"/%s",
		"/content/%s",
		"/read/%s",
	}

	path := helpers.RandomChoice(s.gen, paths)
	slug := s.gen.RandomSlug(4)

	domain := publisher.Domain
	if domain == "" {
		domain = fmt.Sprintf("publisher-%d.com", publisher.ID)
	}

	domain = strings.TrimPrefix(domain, "https://")
	domain = strings.TrimPrefix(domain, "http://")

	return fmt.Sprintf("https://%s%s", domain, fmt.Sprintf(path, slug))
}

func (s *TrafficSimulator) generateKeywords() []string {
	allKeywords := []string{
		"technology", "software", "innovation", "digital", "cloud", "AI", "machine learning",
		"business", "startup", "enterprise", "finance", "investing", "marketing",
		"travel", "food", "health", "fitness", "fashion", "entertainment",
		"deals", "discount", "shopping", "products", "review", "comparison",
		"breaking", "latest", "trending", "update", "analysis", "opinion",
	}

	return helpers.RandomSample(s.gen, allKeywords, s.gen.RandomInt(3, 7))
}

func (s *TrafficSimulator) generatePageTitle(keywords []string) string {
	templates := []string{
		"The Ultimate Guide to %s",
		"Top 10 %s Tips for 2026",
		"How to Master %s in Minutes",
		"Everything You Need to Know About %s",
		"%s: A Complete Overview",
		"Breaking: Latest %s News",
		"Best %s Products Reviewed",
		"Expert Analysis: %s Trends",
	}

	template := helpers.RandomChoice(s.gen, templates)
	keyword := "topics"
	if len(keywords) > 0 {
		keyword = helpers.RandomChoice(s.gen, keywords)
	}

	return fmt.Sprintf(template, titleCase(keyword))
}

func (s *TrafficSimulator) generatePageDescription(keywords []string) string {
	templates := []string{
		"Discover the latest insights on %s. Learn from experts and stay ahead of the curve.",
		"Your comprehensive guide to understanding %s. In-depth analysis and expert recommendations.",
		"Everything you need to know about %s. Updated daily with the latest information.",
		"Expert coverage of %s topics. Trusted by millions of readers worldwide.",
	}

	template := helpers.RandomChoice(s.gen, templates)
	keyword := "various topics"
	if len(keywords) > 0 {
		keyword = strings.Join(keywords[:minInt(3, len(keywords))], ", ")
	}

	return fmt.Sprintf(template, keyword)
}

func (s *TrafficSimulator) selectDeviceType(distribution map[string]float64) string {
	if len(distribution) == 0 {
		return "desktop"
	}

	roll := s.gen.RandomFloat(0, 1)
	cumulative := 0.0

	for device, prob := range distribution {
		cumulative += prob
		if roll <= cumulative {
			return device
		}
	}

	return "desktop"
}

func (s *TrafficSimulator) selectCountry(distribution map[string]float64) string {
	if len(distribution) == 0 {
		return ""
	}

	roll := s.gen.RandomFloat(0, 1)
	cumulative := 0.0

	for country, prob := range distribution {
		cumulative += prob
		if roll <= cumulative {
			return country
		}
	}

	for country := range distribution {
		return country
	}
	return ""
}

func (s *TrafficSimulator) updateCountryStats(country string, update func(*CountryStats)) {
	if country == "" {
		return
	}
	s.stats.mu.Lock()
	defer s.stats.mu.Unlock()

	cs, ok := s.stats.CountryStats[country]
	if !ok {
		cs = &CountryStats{}
		s.stats.CountryStats[country] = cs
	}
	update(cs)
}

func (s *TrafficSimulator) simulateImpression(adResp *client.AdServeResponse, publisherID string) error {
	atomic.AddInt64(&s.stats.TotalImpressions, 1)

	err := s.client.TrackImpression(adResp.ImpressionURL)
	if err != nil {
		atomic.AddInt64(&s.stats.FailedImpressions, 1)
		return err
	}

	atomic.AddInt64(&s.stats.SuccessfulImpressions, 1)
	s.updatePublisherStats(publisherID, func(ps *PublisherStats) {
		ps.Impressions++
	})

	return nil
}

func (s *TrafficSimulator) simulateClick(adResp *client.AdServeResponse, publisherID string) error {
	atomic.AddInt64(&s.stats.TotalClicks, 1)

	err := s.client.TrackClick(adResp.ClickURL)
	if err != nil {
		atomic.AddInt64(&s.stats.FailedClicks, 1)
		return err
	}

	atomic.AddInt64(&s.stats.SuccessfulClicks, 1)
	s.updatePublisherStats(publisherID, func(ps *PublisherStats) {
		ps.Clicks++
	})

	return nil
}

func (s *TrafficSimulator) updateMinMax(latencyMs int64) {
	s.stats.mu.Lock()
	defer s.stats.mu.Unlock()

	if latencyMs < s.stats.MinLatencyMs {
		s.stats.MinLatencyMs = latencyMs
	}
	if latencyMs > s.stats.MaxLatencyMs {
		s.stats.MaxLatencyMs = latencyMs
	}
}

func (s *TrafficSimulator) updatePublisherStats(publisherID string, update func(*PublisherStats)) {
	s.stats.mu.Lock()
	defer s.stats.mu.Unlock()

	ps, ok := s.stats.PublisherStats[publisherID]
	if !ok {
		ps = &PublisherStats{}
		s.stats.PublisherStats[publisherID] = ps
	}
	update(ps)
}

func (s *TrafficSimulator) GetStats() *TrafficStats {
	return s.stats
}

func (s *TrafficSimulator) log(format string, args ...interface{}) {
	if s.verbose {
		fmt.Printf("[Traffic] "+format+"\n", args...)
	}
}

func (s *TrafficSimulator) printSummary(result *TrafficResult) {
	stats := result.Stats

	fmt.Println("\n" + strings.Repeat("=", 60))
	fmt.Println("TRAFFIC SIMULATION COMPLETE - SUMMARY")
	fmt.Println(strings.Repeat("=", 60))
	fmt.Printf("Duration: %v\n\n", result.Duration)

	requestsPerSec := float64(stats.TotalRequests) / result.Duration.Seconds()
	avgLatency := float64(0)
	if stats.SuccessfulRequests > 0 {
		avgLatency = float64(stats.TotalLatencyMs) / float64(stats.TotalRequests)
	}

	fmt.Println("Ad Serve Requests:")
	fmt.Printf("  Total:      %d (%.1f req/sec)\n", stats.TotalRequests, requestsPerSec)
	fmt.Printf("  Successful: %d (%.1f%% fill rate)\n",
		stats.SuccessfulRequests,
		percentage(stats.SuccessfulRequests, stats.TotalRequests))
	fmt.Printf("  No Fill:    %d\n", stats.NoFillRequests)
	fmt.Printf("  Failed:     %d\n", stats.FailedRequests)

	fmt.Println("\nLatency (ms):")
	fmt.Printf("  Average: %.2f\n", avgLatency)
	if stats.MinLatencyMs < int64(^uint64(0)>>1) {
		fmt.Printf("  Min:     %d\n", stats.MinLatencyMs)
	}
	fmt.Printf("  Max:     %d\n", stats.MaxLatencyMs)

	fmt.Println("\nImpressions:")
	fmt.Printf("  Total:      %d\n", stats.TotalImpressions)
	fmt.Printf("  Successful: %d (%.1f%%)\n",
		stats.SuccessfulImpressions,
		percentage(stats.SuccessfulImpressions, stats.TotalImpressions))
	fmt.Printf("  Failed:     %d\n", stats.FailedImpressions)

	fmt.Println("\nClicks:")
	fmt.Printf("  Total:      %d\n", stats.TotalClicks)
	fmt.Printf("  Successful: %d (%.1f%%)\n",
		stats.SuccessfulClicks,
		percentage(stats.SuccessfulClicks, stats.TotalClicks))
	fmt.Printf("  Failed:     %d\n", stats.FailedClicks)

	if stats.SuccessfulImpressions > 0 {
		ctr := float64(stats.SuccessfulClicks) / float64(stats.SuccessfulImpressions) * 100
		fmt.Printf("\nCTR: %.2f%%\n", ctr)
	}

	if len(stats.CountryStats) > 0 {
		fmt.Println("\nPer-Country Breakdown:")
		fmt.Printf("  %-8s %8s %8s %8s %10s\n", "Country", "Requests", "Fills", "NoFills", "Fill Rate")
		for country, cs := range stats.CountryStats {
			fmt.Printf("  %-8s %8d %8d %8d %9.1f%%\n",
				country, cs.Requests, cs.Fills, cs.NoFills,
				percentage(cs.Fills, cs.Requests))
		}
	}

	if len(result.Errors) > 0 {
		fmt.Printf("\nErrors (%d):\n", len(result.Errors))
		maxErrors := 5
		for i, err := range result.Errors {
			if i >= maxErrors {
				fmt.Printf("  ... and %d more errors\n", len(result.Errors)-maxErrors)
				break
			}
			fmt.Printf("  - %v\n", err)
		}
	}

	fmt.Println(strings.Repeat("=", 60))
}

func percentage(part, total int64) float64 {
	if total == 0 {
		return 0
	}
	return float64(part) / float64(total) * 100
}

func minInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func titleCase(s string) string {
	if len(s) == 0 {
		return s
	}
	return strings.ToUpper(s[:1]) + s[1:]
}
