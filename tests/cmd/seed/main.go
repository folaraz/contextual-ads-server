package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"syscall"

	"github.com/folaraz/contextual-ads-server/tests/config"
	"github.com/folaraz/contextual-ads-server/tests/e2e/setup"
)

func main() {
	var (
		configPath  string
		seedAll     bool
		advertisers bool
		publishers  bool
		campaigns   bool
		advCount    int
		pubCount    int
		campCount   int
		dryRun      bool
		verbose     bool
		apiURL      string
		resetDB     bool
		fromFile    string
		workers     int
	)

	flag.StringVar(&configPath, "config", "", "Path to config file (optional)")
	flag.BoolVar(&seedAll, "all", false, "Seed all entities (advertisers, publishers, campaigns)")
	flag.BoolVar(&advertisers, "advertisers", false, "Seed advertisers only")
	flag.BoolVar(&publishers, "publishers", false, "Seed publishers only")
	flag.BoolVar(&campaigns, "campaigns", false, "Seed campaigns only")
	flag.IntVar(&advCount, "adv-count", 0, "Override advertiser count")
	flag.IntVar(&pubCount, "pub-count", 0, "Override publisher count")
	flag.IntVar(&campCount, "camp-count", 0, "Override campaign count")
	flag.BoolVar(&dryRun, "dry-run", false, "Show what would be created without making API calls")
	flag.BoolVar(&verbose, "verbose", false, "Enable verbose output")
	flag.BoolVar(&verbose, "v", false, "Enable verbose output (shorthand)")
	flag.StringVar(&apiURL, "api-url", "", "Override API base URL")
	flag.BoolVar(&resetDB, "reset-db", false, "Reset database (drop, create, migrate) before seeding")
	flag.StringVar(&fromFile, "from-file", "", "Path to pre-generated campaign requests JSON file (e.g., data/campaign_requests_10k.json)")
	flag.IntVar(&workers, "workers", 10, "Number of concurrent workers for file-based seeding (default: 10)")

	flag.Usage = func() {
		fmt.Fprintf(os.Stderr, "Usage: %s [options]\n\n", os.Args[0])
		fmt.Fprintln(os.Stderr, "Seed test data for the Contextual Ads Server E2E tests.")
		fmt.Fprintln(os.Stderr, "\nOptions:")
		flag.PrintDefaults()
		fmt.Fprintln(os.Stderr, "\nExamples:")
		fmt.Fprintln(os.Stderr, "  # Seed all data with default counts")
		fmt.Fprintln(os.Stderr, "  go run ./tests/cmd/seed --all")
		fmt.Fprintln(os.Stderr, "")
		fmt.Fprintln(os.Stderr, "  # Seed with a fresh database (drop, create, migrate)")
		fmt.Fprintln(os.Stderr, "  go run ./tests/cmd/seed --all --reset-db")
		fmt.Fprintln(os.Stderr, "")
		fmt.Fprintln(os.Stderr, "  # Seed only advertisers with custom count")
		fmt.Fprintln(os.Stderr, "  go run ./tests/cmd/seed --advertisers --adv-count=30")
		fmt.Fprintln(os.Stderr, "")
		fmt.Fprintln(os.Stderr, "  # Dry run to see what would be created")
		fmt.Fprintln(os.Stderr, "  go run ./tests/cmd/seed --all --dry-run --verbose")
		fmt.Fprintln(os.Stderr, "")
		fmt.Fprintln(os.Stderr, "  # Use custom config file")
		fmt.Fprintln(os.Stderr, "  go run ./tests/cmd/seed --all --config=tests/config/config.yaml")
		fmt.Fprintln(os.Stderr, "")
		fmt.Fprintln(os.Stderr, "  # Seed from pre-generated 10k campaign file (auto-seeds advertisers + publishers first)")
		fmt.Fprintln(os.Stderr, "  go run ./tests/cmd/seed --from-file=data/campaign_requests_10k.json --workers=10")
		fmt.Fprintln(os.Stderr, "")
		fmt.Fprintln(os.Stderr, "  # Same, with custom advertiser/publisher counts")
		fmt.Fprintln(os.Stderr, "  go run ./tests/cmd/seed --from-file=data/campaign_requests_10k.json --adv-count=241 --pub-count=50")
		fmt.Fprintln(os.Stderr, "")
		fmt.Fprintln(os.Stderr, "  # Dry run file-based seeding")
		fmt.Fprintln(os.Stderr, "  go run ./tests/cmd/seed --from-file=data/campaign_requests_10k.json --dry-run")
	}

	flag.Parse()

	if !seedAll && !advertisers && !publishers && !campaigns && fromFile == "" {
		fmt.Fprintln(os.Stderr, "Error: Must specify at least one of --all, --advertisers, --publishers, --campaigns, or --from-file")
		flag.Usage()
		os.Exit(1)
	}

	cfg, err := config.LoadConfig(configPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error loading config: %v\n", err)
		os.Exit(1)
	}

	if apiURL != "" {
		cfg.API.BaseURL = apiURL
	}
	if advCount > 0 {
		cfg.Seeding.Advertisers.Count = advCount
	}
	if pubCount > 0 {
		cfg.Seeding.Publishers.Count = pubCount
	}
	if campCount > 0 {
		cfg.Seeding.Campaigns.Count = campCount
	}

	printBanner()

	if resetDB {
		if dryRun {
			fmt.Println("DRY RUN: Would reset database (make resetdb)")
		} else {
			fmt.Println("Resetting database...")
			if err := runMakeResetDB(verbose); err != nil {
				fmt.Fprintf(os.Stderr, "Error resetting database: %v\n", err)
				os.Exit(1)
			}
			fmt.Println("Database reset complete\n")
		}
	}

	seeder := setup.NewSeeder(cfg,
		setup.WithVerbose(verbose),
		setup.WithDryRun(dryRun),
	)

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
	go func() {
		<-sigChan
		fmt.Println("\nReceived interrupt signal, cancelling...")
		cancel()
	}()

	if dryRun {
		fmt.Println("DRY RUN MODE - No API calls will be made\n")
	}

	fmt.Printf("API URL: %s\n", cfg.API.BaseURL)
	fmt.Println()

	var exitCode int

	if fromFile != "" {
		var advIDMap map[int]int32
		advFilePath := filepath.Join(filepath.Dir(fromFile), "advertisers_list.json")
		if _, err := os.Stat(advFilePath); err == nil {
			fmt.Printf("=== Phase 1: Seeding Advertisers from file: %s ===\n", advFilePath)
			advResult, idMap, err := seeder.SeedAdvertisersFromFile(ctx, advFilePath)
			if err != nil {
				fmt.Fprintf(os.Stderr, "Error seeding advertisers from file: %v\n", err)
				os.Exit(1)
			}
			advIDMap = idMap
			fmt.Printf("Created %d advertisers (%d failed)\n\n", len(advResult.Advertisers), advResult.Failed)
		} else {
			advSeedCount := cfg.Seeding.Advertisers.Count
			if advCount > 0 {
				advSeedCount = advCount
			}
			fmt.Printf("=== Phase 1: Seeding Advertisers (%d) [no advertisers_list.json found] ===\n", advSeedCount)
			advResult, err := seeder.SeedAdvertisers(ctx, advSeedCount)
			if err != nil {
				fmt.Fprintf(os.Stderr, "Error seeding advertisers: %v\n", err)
				os.Exit(1)
			}
			fmt.Printf("Created %d advertisers (%d failed)\n\n", len(advResult.Advertisers), advResult.Failed)
		}

		pubSeedCount := cfg.Seeding.Publishers.Count
		if pubCount > 0 {
			pubSeedCount = pubCount
		}
		fmt.Printf("=== Phase 2: Seeding Publishers (%d) ===\n", pubSeedCount)
		pubResult, err := seeder.SeedPublishers(ctx, pubSeedCount)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error seeding publishers: %v\n", err)
			os.Exit(1)
		}
		fmt.Printf("Created %d publishers (%d failed)\n\n", len(pubResult.Publishers), pubResult.Failed)

		fmt.Printf("=== Phase 3: Seeding Campaigns from file: %s (workers: %d) ===\n", fromFile, workers)
		result, err := seeder.SeedFromFile(ctx, fromFile, workers, advIDMap)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error: %v\n", err)
			os.Exit(1)
		}
		if result.Failed > 0 {
			fmt.Printf("\nWarning: %d campaigns failed to create\n", result.Failed)
			for i, e := range result.Errors {
				if i >= 10 {
					fmt.Printf("  ... and %d more errors\n", len(result.Errors)-10)
					break
				}
				fmt.Printf("  - %v\n", e)
			}
			exitCode = 1
		}
		os.Exit(exitCode)
	}

	if seedAll {
		result, err := seeder.SeedAll(ctx)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error: %v\n", err)
			exitCode = 1
		} else if len(result.Errors) > 0 {
			exitCode = 1
		}
	} else {
		if advertisers {
			fmt.Println("=== Seeding Advertisers ===")
			result, err := seeder.SeedAdvertisers(ctx, cfg.Seeding.Advertisers.Count)
			if err != nil {
				fmt.Fprintf(os.Stderr, "Error seeding advertisers: %v\n", err)
				exitCode = 1
			} else {
				fmt.Printf("Created %d advertisers (%d failed)\n\n", len(result.Advertisers), result.Failed)
			}
		}

		if publishers {
			fmt.Println("=== Seeding Publishers ===")
			result, err := seeder.SeedPublishers(ctx, cfg.Seeding.Publishers.Count)
			if err != nil {
				fmt.Fprintf(os.Stderr, "Error seeding publishers: %v\n", err)
				exitCode = 1
			} else {
				fmt.Printf("Created %d publishers (%d failed)\n\n", len(result.Publishers), result.Failed)
			}
		}

		if campaigns {
			fmt.Println("=== Seeding Campaigns ===")
			result, err := seeder.SeedCampaigns(ctx, cfg.Seeding.Campaigns.Count)
			if err != nil {
				fmt.Fprintf(os.Stderr, "Error seeding campaigns: %v\n", err)
				exitCode = 1
			} else {
				fmt.Printf("Created %d campaigns (%d failed)\n\n", len(result.Campaigns), result.Failed)
			}
		}
	}

	os.Exit(exitCode)
}

func runMakeResetDB(verbose bool) error {
	cmd := exec.Command("make", "resetdb")

	if verbose {
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr
	}

	return cmd.Run()
}

func printBanner() {
	banner := `
=== Contextual Ads Server - E2E Test Data Seeder ===
               Phase 1: Data Setup
`
	fmt.Println(banner)
}
