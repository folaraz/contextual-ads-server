package main

import (
	"bufio"
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"github.com/folaraz/contextual-ads-server/tests/config"
	"github.com/folaraz/contextual-ads-server/tests/e2e/traffic"
	"github.com/folaraz/contextual-ads-server/tests/fixtures"
)

func main() {
	var (
		configPath     = flag.String("config", "", "Path to config file (uses defaults if not provided)")
		numRequests    = flag.Int("requests", 100, "Number of ad requests to simulate (ignored when -duration is set)")
		concurrency    = flag.Int("concurrency", 10, "Number of concurrent workers")
		rateLimit      = flag.Int("rate", 0, "Requests per second limit (0 = unlimited)")
		impressionRate = flag.Float64("impression-rate", 0.8, "Probability of firing impression (0.0-1.0)")
		clickRate      = flag.Float64("click-rate", 0.03, "Probability of click after impression (0.0-1.0)")
		duration       = flag.Duration("duration", 0, "Run for this duration then stop (e.g. 6h, 30m, 2h30m). Overrides -requests")
		timeout        = flag.Duration("timeout", 10*time.Minute, "Total timeout for simulation (used when -duration is not set)")
		verbose        = flag.Bool("verbose", false, "Enable verbose output")
		dryRun         = flag.Bool("dry-run", false, "Print configuration and exit")
		countries      = flag.String("countries", "US:0.35,GB:0.20,DE:0.15,FR:0.10,CA:0.10,AU:0.10",
			"Country distribution as CODE:WEIGHT pairs (e.g. \"US:0.4,GB:0.3,DE:0.3\")")
		pageURLsFile = flag.String("page-urls-file", "",
			"Path to a text file with page URLs (one per line). Overrides default fixture URLs.")
	)

	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "Traffic Simulator for Contextual Ads Server\n\n")
		fmt.Fprintf(os.Stderr, "Usage: %s [options]\n\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "Options:\n")
		flag.PrintDefaults()
		fmt.Fprintf(os.Stderr, "\nExamples:\n")
		fmt.Fprintf(os.Stderr, "  # Basic test with 100 requests\n")
		fmt.Fprintf(os.Stderr, "  %s -requests 100 -concurrency 10\n\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "  # High volume test with rate limiting\n")
		fmt.Fprintf(os.Stderr, "  %s -requests 1000 -concurrency 50 -rate 100\n\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "  # Run for 6 hours with 50 workers\n")
		fmt.Fprintf(os.Stderr, "  %s -duration 6h -concurrency 50\n\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "  # Run for 30 minutes with rate limiting\n")
		fmt.Fprintf(os.Stderr, "  %s -duration 30m -concurrency 20 -rate 500\n\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "  # Burst test\n")
		fmt.Fprintf(os.Stderr, "  %s -requests 500 -concurrency 100 -rate 0\n\n", os.Args[0])
		fmt.Fprintf(os.Stderr, "  # Geo-distributed test\n")
		fmt.Fprintf(os.Stderr, "  %s -requests 1000 -countries \"US:0.5,GB:0.3,DE:0.2\"\n\n", os.Args[0])
	}

	flag.Parse()

	cfg, err := config.LoadConfig(*configPath)
	if err != nil {
		log.Fatalf("Failed to load config: %v", err)
	}

	countryDist := parseCountryDistribution(*countries)

	pageURLs := fixtures.AllPageURLs()
	if *pageURLsFile != "" {
		loaded, err := loadPageURLsFromFile(*pageURLsFile)
		if err != nil {
			log.Fatalf("Failed to load page URLs from %s: %v", *pageURLsFile, err)
		}
		if len(loaded) == 0 {
			log.Fatalf("No URLs found in %s", *pageURLsFile)
		}
		pageURLs = loaded
		fmt.Printf("Loaded %d page URLs from %s\n", len(pageURLs), *pageURLsFile)
	}

	trafficCfg := traffic.TrafficConfig{
		NumRequests:    *numRequests,
		Concurrency:    *concurrency,
		RateLimit:      *rateLimit,
		ImpressionRate: *impressionRate,
		ClickRate:      *clickRate,
		DeviceDistribution: map[string]float64{
			"desktop": 0.45,
			"mobile":  0.45,
			"tablet":  0.10,
		},
		CountryDistribution: countryDist,
		PageURLs:            pageURLs,
	}

	if *duration > 0 {
		trafficCfg.Duration = *duration
		trafficCfg.NumRequests = 0
	}

	fmt.Println("Traffic Simulation Configuration")
	fmt.Println("================================")
	fmt.Printf("API Base URL:     %s\n", cfg.API.BaseURL)
	if trafficCfg.Duration > 0 {
		fmt.Printf("Mode:             duration-based (run for %v)\n", trafficCfg.Duration)
	} else {
		fmt.Printf("Mode:             request-count (%d requests)\n", trafficCfg.NumRequests)
	}
	fmt.Printf("Concurrency:      %d\n", trafficCfg.Concurrency)
	fmt.Printf("Rate Limit:       %d req/sec", trafficCfg.RateLimit)
	if trafficCfg.RateLimit == 0 {
		fmt.Print(" (unlimited)")
	}
	fmt.Println()
	fmt.Printf("Impression Rate:  %.1f%%\n", trafficCfg.ImpressionRate*100)
	fmt.Printf("Click Rate:       %.1f%%\n", trafficCfg.ClickRate*100)
	if len(trafficCfg.CountryDistribution) > 0 {
		fmt.Printf("Countries:        ")
		first := true
		for code, weight := range trafficCfg.CountryDistribution {
			if !first {
				fmt.Print(", ")
			}
			fmt.Printf("%s:%.0f%%", code, weight*100)
			first = false
		}
		fmt.Println()
	}
	fmt.Printf("Timeout:          %v\n", *timeout)
	fmt.Printf("Verbose:          %v\n", *verbose)
	fmt.Println()

	if *dryRun {
		fmt.Println("Dry run mode - exiting.")
		return
	}

	simulator := traffic.NewTrafficSimulator(cfg,
		traffic.WithVerboseSimulator(*verbose),
	)

	ctxTimeout := *timeout
	if *duration > 0 {
		ctxTimeout = *duration
	}
	ctx, cancel := context.WithTimeout(context.Background(), ctxTimeout)
	defer cancel()

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	go func() {
		<-sigCh
		fmt.Println("\nReceived interrupt signal, shutting down...")
		cancel()
	}()

	fmt.Println("Starting traffic simulation...")
	fmt.Println()

	result, err := simulator.Run(ctx, trafficCfg)
	if err != nil {
		log.Fatalf("Simulation failed: %v", err)
	}

	errorRate := float64(result.Stats.FailedRequests) / float64(result.Stats.TotalRequests)
	if errorRate > 0.05 {
		fmt.Printf("\nWARNING: High error rate (%.1f%%)\n", errorRate*100)
		os.Exit(1)
	}

	fmt.Println("\nSimulation completed successfully!")
}

func loadPageURLsFromFile(path string) ([]string, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	var urls []string
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line != "" && !strings.HasPrefix(line, "#") {
			urls = append(urls, line)
		}
	}
	return urls, scanner.Err()
}

func parseCountryDistribution(s string) map[string]float64 {
	s = strings.TrimSpace(s)
	if s == "" {
		return nil
	}

	result := make(map[string]float64)
	for _, pair := range strings.Split(s, ",") {
		pair = strings.TrimSpace(pair)
		parts := strings.SplitN(pair, ":", 2)
		if len(parts) != 2 {
			log.Fatalf("Invalid country distribution entry: %q (expected CODE:WEIGHT)", pair)
		}
		code := strings.TrimSpace(strings.ToUpper(parts[0]))
		weight, err := strconv.ParseFloat(strings.TrimSpace(parts[1]), 64)
		if err != nil {
			log.Fatalf("Invalid weight for country %s: %v", code, err)
		}
		result[code] = weight
	}
	return result
}
