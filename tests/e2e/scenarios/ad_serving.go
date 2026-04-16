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

type AdServingScenario struct {
	client  *client.Client
	config  *config.Config
	gen     *helpers.Generator
	verbose bool
}

func NewAdServingScenario(cfg *config.Config, verbose bool) *AdServingScenario {
	c := client.NewClient(cfg)
	c.SetVerbose(verbose)

	return &AdServingScenario{
		client:  c,
		config:  cfg,
		gen:     helpers.NewGenerator(),
		verbose: verbose,
	}
}

type AdServeTestCase struct {
	Name        string
	PublisherID string
	PageURL     string
	Keywords    []string
	Title       string
	Description string
	DeviceType  string
	Language    string

	ExpectFill bool
}

type AdServeResult struct {
	TestCase     AdServeTestCase
	Response     *client.AdServeResponse
	RawResponse  interface{}
	StatusCode   int
	Latency      time.Duration
	Error        error
	HasFill      bool
	ImpressionOK bool
	ClickOK      bool
}

func (s *AdServingScenario) RunTestCase(tc AdServeTestCase) *AdServeResult {
	result := &AdServeResult{
		TestCase: tc,
	}

	req := client.AdServeRequest{
		PublisherID: tc.PublisherID,
		Context: client.AdContext{
			URL:         tc.PageURL,
			Keywords:    tc.Keywords,
			Title:       tc.Title,
			Description: tc.Description,
		},
		Device: client.DeviceInfo{
			Type:      tc.DeviceType,
			UserAgent: s.gen.RandomUserAgent(tc.DeviceType),
			Language:  tc.Language,
		},
		Meta: client.RequestMeta{
			Timestamp: time.Now().Unix(),
		},
	}

	s.log("Running test case: %s", tc.Name)
	s.log("  Publisher: %s", tc.PublisherID)
	s.log("  URL: %s", tc.PageURL)
	s.log("  Keywords: %v", tc.Keywords)

	start := time.Now()
	resp, err := s.client.ServeAd(req)
	result.Latency = time.Since(start)

	if err != nil {
		if strings.Contains(err.Error(), "204") || strings.Contains(err.Error(), "no content") {
			result.HasFill = false
			s.log("  Result: No Fill (204)")
		} else {
			result.Error = err
			s.log("  Result: Error - %v", err)
		}
		return result
	}

	result.Response = resp
	result.HasFill = true
	s.log("  Result: Fill (Ad ID: %d)", getAdID(resp))
	s.log("  Latency: %v", result.Latency)

	if resp.ImpressionURL != "" {
		s.log("  Impression URL: present")
	}
	if resp.ClickURL != "" {
		s.log("  Click URL: present")
	}

	return result
}

func (s *AdServingScenario) RunAllTestCases(ctx context.Context, testCases []AdServeTestCase) []*AdServeResult {
	results := make([]*AdServeResult, 0, len(testCases))

	for _, tc := range testCases {
		select {
		case <-ctx.Done():
			return results
		default:
		}

		result := s.RunTestCase(tc)
		results = append(results, result)
	}

	return results
}

func (s *AdServingScenario) GenerateTestCases(publishers []client.Publisher, count int) []AdServeTestCase {
	testCases := make([]AdServeTestCase, 0, count)

	deviceTypes := []string{"desktop", "mobile", "tablet"}
	keywordSets := [][]string{
		{"technology", "software", "innovation"},
		{"shopping", "deals", "discount", "buy"},
		{"travel", "vacation", "destinations"},
		{"finance", "investing", "stocks"},
		{"health", "fitness", "wellness"},
		{"entertainment", "movies", "streaming"},
		{"education", "learning", "courses"},
		{"food", "recipes", "cooking"},
	}

	for i := 0; i < count; i++ {
		publisher := helpers.RandomChoice(s.gen, publishers)
		deviceType := helpers.RandomChoice(s.gen, deviceTypes)
		keywords := helpers.RandomChoice(s.gen, keywordSets)

		domain := publisher.Domain
		if domain == "" {
			domain = fmt.Sprintf("publisher-%d.com", publisher.ID)
		}

		pageURL := fmt.Sprintf("https://%s/article/%s", domain, s.gen.RandomSlug(3))

		tc := AdServeTestCase{
			Name:        fmt.Sprintf("Test_%d_%s_%s", i+1, deviceType, keywords[0]),
			PublisherID: fmt.Sprintf("%d", publisher.ID),
			PageURL:     pageURL,
			Keywords:    keywords,
			Title:       fmt.Sprintf("Article about %s", keywords[0]),
			Description: fmt.Sprintf("Learn more about %s and related topics.", strings.Join(keywords, ", ")),
			DeviceType:  deviceType,
			Language:    "en-US",
			ExpectFill:  true,
		}

		testCases = append(testCases, tc)
	}

	return testCases
}

func (s *AdServingScenario) PrintSummary(results []*AdServeResult) {
	fmt.Println("\n" + strings.Repeat("=", 60))
	fmt.Println("AD SERVING SCENARIO - SUMMARY")
	fmt.Println(strings.Repeat("=", 60))

	var totalTests, fills, noFills, errors int
	var totalLatency time.Duration
	var minLatency, maxLatency time.Duration

	minLatency = time.Hour

	for _, r := range results {
		totalTests++
		totalLatency += r.Latency

		if r.Latency < minLatency {
			minLatency = r.Latency
		}
		if r.Latency > maxLatency {
			maxLatency = r.Latency
		}

		if r.Error != nil {
			errors++
		} else if r.HasFill {
			fills++
		} else {
			noFills++
		}
	}

	fmt.Printf("\nTotal Tests: %d\n", totalTests)
	fmt.Printf("  Fills:    %d (%.1f%%)\n", fills, float64(fills)/float64(totalTests)*100)
	fmt.Printf("  No Fills: %d (%.1f%%)\n", noFills, float64(noFills)/float64(totalTests)*100)
	fmt.Printf("  Errors:   %d (%.1f%%)\n", errors, float64(errors)/float64(totalTests)*100)

	if totalTests > 0 {
		fmt.Printf("\nLatency:\n")
		fmt.Printf("  Average: %v\n", totalLatency/time.Duration(totalTests))
		fmt.Printf("  Min:     %v\n", minLatency)
		fmt.Printf("  Max:     %v\n", maxLatency)
	}

	fmt.Println(strings.Repeat("=", 60))
}

func (s *AdServingScenario) log(format string, args ...interface{}) {
	if s.verbose {
		fmt.Printf(format+"\n", args...)
	}
}

func getAdID(resp *client.AdServeResponse) int32 {
	if resp == nil {
		return 0
	}
	return resp.Ad.ID
}
