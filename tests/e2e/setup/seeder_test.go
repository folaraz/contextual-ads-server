package setup_test

import (
	"context"
	"errors"
	"os"
	"testing"
	"time"

	"github.com/folaraz/contextual-ads-server/tests/config"
	"github.com/folaraz/contextual-ads-server/tests/e2e/setup"
	"github.com/folaraz/contextual-ads-server/tests/helpers"
)

func getTestConfig() *config.Config {
	cfg := config.DefaultConfig()

	if url := os.Getenv("TEST_API_URL"); url != "" {
		cfg.API.BaseURL = url
	}

	cfg.Seeding.Advertisers.Count = 5
	cfg.Seeding.Publishers.Count = 10
	cfg.Seeding.Campaigns.Count = 15

	return cfg
}

func skipIfNoAPI(t *testing.T, cfg *config.Config) {
	t.Helper()
	seeder := setup.NewSeeder(cfg)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	_, err := seeder.SeedAdvertisers(ctx, 0)
	if err != nil && err.Error() != "no advertisers available to create campaigns for" {
		t.Skipf("Skipping test: API not available at %s", cfg.API.BaseURL)
	}
}

func TestSeeder_SeedAdvertisers(t *testing.T) {
	cfg := getTestConfig()
	skipIfNoAPI(t, cfg)

	seeder := setup.NewSeeder(cfg, setup.WithVerbose(true))

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	result, err := seeder.SeedAdvertisers(ctx, 3)
	helpers.RequireNoError(t, err, "seeding advertisers should not error")
	helpers.AssertEqual(t, 3, len(result.Advertisers)+result.Failed, "should attempt to create 3 advertisers")
	helpers.AssertGreater(t, len(result.Advertisers), 0, "should create at least one advertiser")

	for _, adv := range result.Advertisers {
		helpers.AssertGreater(t, adv.ID, int32(0), "advertiser should have positive ID")
		helpers.AssertTrue(t, adv.Name != "", "advertiser should have name")
	}
}

func TestSeeder_SeedPublishers(t *testing.T) {
	cfg := getTestConfig()
	skipIfNoAPI(t, cfg)

	seeder := setup.NewSeeder(cfg, setup.WithVerbose(true))

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	result, err := seeder.SeedPublishers(ctx, 5)
	helpers.RequireNoError(t, err, "seeding publishers should not error")
	helpers.AssertEqual(t, 5, len(result.Publishers)+result.Failed, "should attempt to create 5 publishers")
	helpers.AssertGreater(t, len(result.Publishers), 0, "should create at least one publisher")

	for _, pub := range result.Publishers {
		helpers.AssertGreater(t, pub.ID, int32(0), "publisher should have positive ID")
		helpers.AssertTrue(t, pub.Name != "", "publisher should have name")
		helpers.AssertTrue(t, pub.Domain != "", "publisher should have domain")
	}
}

func TestSeeder_SeedCampaigns(t *testing.T) {
	cfg := getTestConfig()
	skipIfNoAPI(t, cfg)

	seeder := setup.NewSeeder(cfg, setup.WithVerbose(true))

	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()

	advResult, err := seeder.SeedAdvertisers(ctx, 2)
	helpers.RequireNoError(t, err, "seeding advertisers should not error")
	helpers.AssertGreater(t, len(advResult.Advertisers), 0, "need advertisers for campaigns")

	result, err := seeder.SeedCampaigns(ctx, 3)
	helpers.RequireNoError(t, err, "seeding campaigns should not error")
	helpers.AssertEqual(t, 3, len(result.Campaigns)+result.Failed, "should attempt to create 3 campaigns")

	for _, camp := range result.Campaigns {
		helpers.AssertGreater(t, camp.CampaignID, int32(0), "campaign should have positive ID")
		helpers.AssertGreater(t, camp.AdSetID, int32(0), "ad set should have positive ID")
		helpers.AssertGreater(t, camp.AdID, int32(0), "ad should have positive ID")
	}
}

func TestSeeder_SeedAll(t *testing.T) {
	cfg := getTestConfig()
	skipIfNoAPI(t, cfg)

	cfg.Seeding.Advertisers.Count = 10
	cfg.Seeding.Publishers.Count = 10
	cfg.Seeding.Campaigns.Count = 10

	seeder := setup.NewSeeder(cfg, setup.WithVerbose(true))

	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	result, err := seeder.SeedAll(ctx)
	helpers.RequireNoError(t, err, "seeding all should not error")

	helpers.AssertGreater(t, result.Stats.AdvertisersCreated, 0, "should create advertisers")
	helpers.AssertGreater(t, result.Stats.PublishersCreated, 0, "should create publishers")
	helpers.AssertGreater(t, result.Stats.CampaignsCreated, 0, "should create campaigns")

	helpers.AssertEqual(t, len(result.Advertisers), result.Stats.AdvertisersCreated, "result advertisers should match count")
	helpers.AssertEqual(t, len(result.Publishers), result.Stats.PublishersCreated, "result publishers should match count")
	helpers.AssertEqual(t, len(result.Campaigns), result.Stats.CampaignsCreated, "result campaigns should match count")
}

func TestSeeder_Cancellation(t *testing.T) {
	cfg := getTestConfig()
	cfg.Seeding.Advertisers.Count = 100

	seeder := setup.NewSeeder(cfg, setup.WithVerbose(false))

	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()

	_, err := seeder.SeedAdvertisers(ctx, 100)

	if err != nil {
		helpers.AssertTrue(t, errors.Is(err, context.DeadlineExceeded) || errors.Is(err, context.Canceled),
			"should be cancelled by context")
	}
}
