package setup

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/folaraz/contextual-ads-server/tests/client"
	"github.com/folaraz/contextual-ads-server/tests/config"
	"github.com/folaraz/contextual-ads-server/tests/fixtures"
	"github.com/folaraz/contextual-ads-server/tests/helpers"
)

type Seeder struct {
	client  *client.Client
	config  *config.Config
	gen     *helpers.Generator
	verbose bool
	dryRun  bool

	mu          sync.RWMutex
	advertisers []client.Advertiser
	publishers  []client.Publisher
	campaigns   []client.CreateCampaignResponse
}

type SeederOption func(*Seeder)

func WithVerbose(verbose bool) SeederOption {
	return func(s *Seeder) {
		s.verbose = verbose
	}
}

func WithDryRun(dryRun bool) SeederOption {
	return func(s *Seeder) {
		s.dryRun = dryRun
	}
}

func NewSeeder(cfg *config.Config, opts ...SeederOption) *Seeder {
	s := &Seeder{
		client:      client.NewClient(cfg),
		config:      cfg,
		gen:         helpers.NewGenerator(),
		advertisers: make([]client.Advertiser, 0),
		publishers:  make([]client.Publisher, 0),
		campaigns:   make([]client.CreateCampaignResponse, 0),
	}

	for _, opt := range opts {
		opt(s)
	}

	s.client.SetVerbose(s.verbose)
	return s
}

type SeedingResult struct {
	Advertisers []client.Advertiser
	Publishers  []client.Publisher
	Campaigns   []client.CreateCampaignResponse
	Errors      []error
	Duration    time.Duration
	Stats       SeedingStats
}

type SeedingStats struct {
	AdvertisersCreated        int
	AdvertisersFailed         int
	PublishersCreated         int
	PublishersFailed          int
	CampaignsCreated          int
	CampaignsFailed           int
	CompetingCampaignsCreated int
	CompetingCampaignsFailed  int
}

func (s *Seeder) SeedAll(ctx context.Context) (*SeedingResult, error) {
	start := time.Now()
	result := &SeedingResult{
		Errors: make([]error, 0),
	}

	s.log("Starting full data seeding...")
	s.log("Configuration:")
	s.log("  - Advertisers: %d", s.config.Seeding.Advertisers.Count)
	s.log("  - Publishers: %d", s.config.Seeding.Publishers.Count)
	s.log("  - Campaigns: %d", s.config.Seeding.Campaigns.Count)

	s.log("\n=== Phase 1.1: Seeding Advertisers ===")
	advResult, err := s.SeedAdvertisers(ctx, s.config.Seeding.Advertisers.Count)
	if err != nil {
		return nil, fmt.Errorf("failed to seed advertisers: %w", err)
	}
	result.Advertisers = advResult.Advertisers
	result.Stats.AdvertisersCreated = len(advResult.Advertisers)
	result.Stats.AdvertisersFailed = advResult.Failed
	result.Errors = append(result.Errors, advResult.Errors...)

	s.log("\n=== Phase 1.2: Seeding Publishers ===")
	pubResult, err := s.SeedPublishers(ctx, s.config.Seeding.Publishers.Count)
	if err != nil {
		return nil, fmt.Errorf("failed to seed publishers: %w", err)
	}
	result.Publishers = pubResult.Publishers
	result.Stats.PublishersCreated = len(pubResult.Publishers)
	result.Stats.PublishersFailed = pubResult.Failed
	result.Errors = append(result.Errors, pubResult.Errors...)

	s.log("\n=== Phase 1.3: Seeding Campaigns ===")
	campResult, err := s.SeedCampaigns(ctx, s.config.Seeding.Campaigns.Count)
	if err != nil {
		return nil, fmt.Errorf("failed to seed campaigns: %w", err)
	}
	result.Campaigns = campResult.Campaigns
	result.Stats.CampaignsCreated = len(campResult.Campaigns)
	result.Stats.CampaignsFailed = campResult.Failed
	result.Errors = append(result.Errors, campResult.Errors...)

	s.log("\n=== Phase 1.4: Seeding Competing Campaigns ===")
	compResult, err := s.SeedCompetingCampaigns(ctx, 10)
	if err != nil {
		s.log("Warning: failed to seed competing campaigns: %v", err)
	} else {
		result.Campaigns = append(result.Campaigns, compResult.Campaigns...)
		result.Stats.CompetingCampaignsCreated = len(compResult.Campaigns)
		result.Stats.CompetingCampaignsFailed = compResult.Failed
		result.Errors = append(result.Errors, compResult.Errors...)
	}

	result.Duration = time.Since(start)

	s.printSummary(result)

	return result, nil
}

type AdvertiserSeedResult struct {
	Advertisers []client.Advertiser
	Failed      int
	Errors      []error
}

func (s *Seeder) SeedAdvertisers(ctx context.Context, count int) (*AdvertiserSeedResult, error) {
	result := &AdvertiserSeedResult{
		Advertisers: make([]client.Advertiser, 0, count),
		Errors:      make([]error, 0),
	}

	industries := s.config.Seeding.Advertisers.Industries
	if len(industries) == 0 {
		industries = []string{"e-commerce", "saas", "entertainment", "education", "finance"}
	}

	s.log("Creating %d advertisers across %d industries...", count, len(industries))

	for i := 0; i < count; i++ {
		select {
		case <-ctx.Done():
			return result, ctx.Err()
		default:
		}

		industry := helpers.RandomChoice(s.gen, industries)
		templates := fixtures.GetAdvertiserTemplates(industry)
		template := helpers.RandomChoice(s.gen, templates)

		suffix := fmt.Sprintf("%d", i+1)
		req := template.ToCreateRequest(suffix)

		if s.dryRun {
			s.log("  [DRY RUN] Would create advertiser: %s (%s)", req.Name, industry)
			continue
		}

		advertiser, err := s.client.CreateAdvertiser(req)
		if err != nil {
			result.Failed++
			result.Errors = append(result.Errors, fmt.Errorf("failed to create advertiser %s: %w", req.Name, err))
			s.log("  ✗ Failed to create: %s - %v", req.Name, err)
			continue
		}

		result.Advertisers = append(result.Advertisers, *advertiser)
		s.log("  ✓ Created advertiser: %s (ID: %d)", advertiser.Name, advertiser.ID)

		s.mu.Lock()
		s.advertisers = append(s.advertisers, *advertiser)
		s.mu.Unlock()
	}

	s.log("Advertisers seeding complete: %d created, %d failed", len(result.Advertisers), result.Failed)
	return result, nil
}

type FileAdvertiser struct {
	ID       int    `json:"id"`
	Name     string `json:"name"`
	Website  string `json:"website"`
	Industry string `json:"industry"`
}

func (s *Seeder) SeedAdvertisersFromFile(ctx context.Context, filePath string) (*AdvertiserSeedResult, map[int]int32, error) {
	data, err := os.ReadFile(filePath)
	if err != nil {
		return nil, nil, fmt.Errorf("failed to read advertisers file %s: %w", filePath, err)
	}

	var fileAdvertisers []FileAdvertiser
	if err := json.Unmarshal(data, &fileAdvertisers); err != nil {
		return nil, nil, fmt.Errorf("failed to parse advertisers file: %w", err)
	}

	result := &AdvertiserSeedResult{
		Advertisers: make([]client.Advertiser, 0, len(fileAdvertisers)),
		Errors:      make([]error, 0),
	}
	idMap := make(map[int]int32, len(fileAdvertisers))

	s.log("Creating %d advertisers from file %s...", len(fileAdvertisers), filePath)

	for i, fa := range fileAdvertisers {
		select {
		case <-ctx.Done():
			return result, idMap, ctx.Err()
		default:
		}

		req := client.CreateAdvertiserRequest{
			Name:    fa.Name,
			Website: fa.Website,
		}

		if s.dryRun {
			s.log("  [DRY RUN] Would create advertiser: %s (%s)", fa.Name, fa.Industry)
			continue
		}

		advertiser, err := s.client.CreateAdvertiser(req)
		if err != nil {
			result.Failed++
			result.Errors = append(result.Errors, fmt.Errorf("failed to create advertiser %d (%s): %w", fa.ID, fa.Name, err))
			s.log("  ✗ Failed to create: %s - %v", fa.Name, err)
			continue
		}

		idMap[fa.ID] = advertiser.ID
		result.Advertisers = append(result.Advertisers, *advertiser)
		s.log("  ✓ Created advertiser: %s (file ID: %d → DB ID: %d)", advertiser.Name, fa.ID, advertiser.ID)

		s.mu.Lock()
		s.advertisers = append(s.advertisers, *advertiser)
		s.mu.Unlock()

		if (i+1)%100 == 0 {
			fmt.Printf("  Progress: %d/%d advertisers created\n", i+1, len(fileAdvertisers))
		}
	}

	s.log("Advertisers from file seeding complete: %d created, %d failed", len(result.Advertisers), result.Failed)
	return result, idMap, nil
}

type PublisherSeedResult struct {
	Publishers []client.Publisher
	Failed     int
	Errors     []error
}

func (s *Seeder) SeedPublishers(ctx context.Context, count int) (*PublisherSeedResult, error) {
	result := &PublisherSeedResult{
		Publishers: make([]client.Publisher, 0, count),
		Errors:     make([]error, 0),
	}

	categories := s.config.Seeding.Publishers.Categories
	if len(categories) == 0 {
		categories = []string{"news", "blog", "e-commerce", "entertainment", "sports", "technology"}
	}

	s.log("Creating %d publishers across %d categories...", count, len(categories))

	for i := 0; i < count; i++ {
		select {
		case <-ctx.Done():
			return result, ctx.Err()
		default:
		}

		category := helpers.RandomChoice(s.gen, categories)
		templates := fixtures.GetPublisherTemplates(category)
		template := helpers.RandomChoice(s.gen, templates)

		suffix := fmt.Sprintf("%d", i+1)
		req := template.ToCreateRequest(suffix)

		if s.dryRun {
			s.log("  [DRY RUN] Would create publisher: %s (%s)", req.Name, category)
			continue
		}

		publisher, err := s.client.CreatePublisher(req)
		if err != nil {
			result.Failed++
			result.Errors = append(result.Errors, fmt.Errorf("failed to create publisher %s: %w", req.Name, err))
			s.log("  ✗ Failed to create: %s - %v", req.Name, err)
			continue
		}

		result.Publishers = append(result.Publishers, *publisher)
		s.log("  ✓ Created publisher: %s (ID: %d)", publisher.Name, publisher.ID)

		s.mu.Lock()
		s.publishers = append(s.publishers, *publisher)
		s.mu.Unlock()
	}

	s.log("Publishers seeding complete: %d created, %d failed", len(result.Publishers), result.Failed)
	return result, nil
}

type CampaignSeedResult struct {
	Campaigns []client.CreateCampaignResponse
	Failed    int
	Errors    []error
}

func (s *Seeder) SeedCampaigns(ctx context.Context, count int) (*CampaignSeedResult, error) {
	result := &CampaignSeedResult{
		Campaigns: make([]client.CreateCampaignResponse, 0, count),
		Errors:    make([]error, 0),
	}

	s.mu.RLock()
	advertisers := s.advertisers
	s.mu.RUnlock()

	if len(advertisers) == 0 {
		existingAdvertisers, err := s.client.ListAdvertisers()
		if err != nil {
			return nil, fmt.Errorf("no advertisers available and failed to fetch: %w", err)
		}
		advertisers = existingAdvertisers
		s.mu.Lock()
		s.advertisers = advertisers
		s.mu.Unlock()
	}

	if len(advertisers) == 0 {
		return nil, fmt.Errorf("no advertisers available to create campaigns for")
	}

	cfg := s.config.Seeding.Campaigns
	industries := s.config.Seeding.Advertisers.Industries
	if len(industries) == 0 {
		industries = []string{"e-commerce", "saas", "entertainment", "education", "finance"}
	}

	s.log("Creating %d campaigns for %d advertisers...", count, len(advertisers))

	for i := 0; i < count; i++ {
		select {
		case <-ctx.Done():
			return result, ctx.Err()
		default:
		}

		advertiser := helpers.RandomChoice(s.gen, advertisers)

		industry := helpers.RandomChoice(s.gen, industries)

		req := s.generateCampaignRequest(advertiser.ID, industry, cfg, i+1)

		if s.dryRun {
			s.log("  [DRY RUN] Would create campaign: %s for advertiser %d", req.Campaign.Name, advertiser.ID)
			continue
		}

		campaign, err := s.client.CreateCampaign(req)
		if err != nil {
			result.Failed++
			result.Errors = append(result.Errors, fmt.Errorf("failed to create campaign %s: %w", req.Campaign.Name, err))
			s.log("  ✗ Failed to create: %s - %v", req.Campaign.Name, err)
			continue
		}

		result.Campaigns = append(result.Campaigns, *campaign)
		s.log("  ✓ Created campaign: %s (Campaign ID: %d, Ad ID: %d)", req.Campaign.Name, campaign.CampaignID, campaign.AdID)

		s.mu.Lock()
		s.campaigns = append(s.campaigns, *campaign)
		s.mu.Unlock()
	}

	s.log("Campaigns seeding complete: %d created, %d failed", len(result.Campaigns), result.Failed)
	return result, nil
}

func (s *Seeder) generateCampaignRequest(advertiserID int32, industry string, cfg config.CampaignSeedConfig,
	index int) client.CreateCampaignRequest {
	budget := s.gen.RandomBudget(cfg.BudgetRange.Min, cfg.BudgetRange.Max)

	pricingModel := helpers.RandomChoice(s.gen, cfg.PricingModels)

	bidAmount := s.gen.RandomBidAmount(
		pricingModel,
		[2]float64{cfg.BidAmountRange.CPM.Min, cfg.BidAmountRange.CPM.Max},
		[2]float64{cfg.BidAmountRange.CPC.Min, cfg.BidAmountRange.CPC.Max},
	)

	dailyBudget := budget * cfg.DailyBudgetPct

	startDate, endDate := s.gen.RandomDateRange(cfg.DurationDays.Min, cfg.DurationDays.Max)

	status := helpers.RandomChoice(s.gen, cfg.CampaignStatuses)

	targeting := fixtures.GetTargetingData(industry)

	creativeTemplates := fixtures.GetCreativeTemplates(industry)
	creativeTemplate := helpers.RandomChoice(s.gen, creativeTemplates)
	imageURLs := fixtures.GetImageURLs(industry)

	industryCapitalized := strings.ToUpper(industry[:1]) + industry[1:]
	campaignName := fmt.Sprintf("%s Campaign %d", industryCapitalized, index)

	keyword := "products"
	if len(targeting.Keywords) > 0 {
		keyword = helpers.RandomChoice(s.gen, targeting.Keywords)
	}

	creative := fixtures.CreativeData{
		Headline:       fmt.Sprintf(creativeTemplate.HeadlineTemplate, keyword),
		Description:    fmt.Sprintf(creativeTemplate.DescriptionTemplate, keyword),
		ImageURL:       helpers.RandomChoice(s.gen, imageURLs),
		CallToAction:   helpers.RandomChoice(s.gen, creativeTemplate.CTAs),
		LandingPageURL: fmt.Sprintf("https://www.example-%d.com/%s", advertiserID, s.gen.RandomSlug(3)),
		CreativeType:   "banner",
	}

	selectedKeywords := helpers.RandomSample(s.gen, targeting.Keywords, s.gen.RandomInt(3, 7))
	selectedCountries := helpers.RandomSample(s.gen, cfg.Countries, s.gen.RandomInt(1, 3))
	selectedDevices := helpers.RandomSample(s.gen, cfg.Devices, s.gen.RandomInt(1, 3))

	return fixtures.BuildCampaignRequest(
		advertiserID,
		campaignName,
		status,
		budget,
		bidAmount,
		dailyBudget,
		pricingModel,
		helpers.FormatDate(startDate),
		helpers.FormatDate(endDate),
		creative,
		fixtures.TargetingData{
			Keywords: selectedKeywords,
			Topics:   targeting.Topics,
			Entities: targeting.Entities,
		},
		selectedCountries,
		selectedDevices,
	)
}

type CompetingCampaignSeedResult struct {
	Campaigns []client.CreateCampaignResponse
	Failed    int
	Errors    []error
}

func (s *Seeder) SeedCompetingCampaigns(ctx context.Context, count int) (*CompetingCampaignSeedResult, error) {
	result := &CompetingCampaignSeedResult{
		Campaigns: make([]client.CreateCampaignResponse, 0, count),
		Errors:    make([]error, 0),
	}

	s.mu.RLock()
	advertisers := s.advertisers
	s.mu.RUnlock()

	if len(advertisers) == 0 {
		existingAdvertisers, err := s.client.ListAdvertisers()
		if err != nil {
			return nil, fmt.Errorf("no advertisers available: %w", err)
		}
		advertisers = existingAdvertisers
	}

	if len(advertisers) == 0 {
		return nil, fmt.Errorf("no advertisers available to create competing campaigns")
	}

	sharedKeywords := []string{
		"technology", "software", "cloud", "AI", "innovation",
		"machine learning", "digital", "automation", "analytics", "data",
	}
	sharedCountries := []string{"US", "CA", "GB"}
	sharedDevices := []string{"desktop", "mobile", "tablet"}
	sharedTopics := []int32{602, 603, 604}
	sharedEntities := []fixtures.EntityData{
		{Type: "BRAND", Name: "Google"},
		{Type: "BRAND", Name: "Microsoft"},
		{Type: "PRODUCT", Name: "cloud platform"},
		{Type: "ORGANIZATION", Name: "tech company"},
	}

	startDate := helpers.FormatDate(time.Now().AddDate(0, 0, -3))
	endDate := helpers.FormatDate(time.Now().AddDate(0, 0, 60))

	industries := []string{"technology", "saas", "e-commerce", "finance", "entertainment"}

	s.log("Creating %d competing campaigns with shared targeting...", count)

	for i := 0; i < count; i++ {
		select {
		case <-ctx.Done():
			return result, ctx.Err()
		default:
		}

		advertiser := advertisers[i%len(advertisers)]
		industry := industries[i%len(industries)]

		bidAmount := 2.0 + float64(i)*1.5
		budget := 5000.0 + float64(i)*1000.0

		pricingModel := "CPM"
		if i%3 == 0 {
			pricingModel = "CPC"
			bidAmount = 0.5 + float64(i)*0.3
		}

		creativeTemplates := fixtures.GetCreativeTemplates(industry)
		template := helpers.RandomChoice(s.gen, creativeTemplates)
		imageURLs := fixtures.GetImageURLs(industry)
		keyword := helpers.RandomChoice(s.gen, sharedKeywords)

		creative := fixtures.CreativeData{
			Headline:       fmt.Sprintf(template.HeadlineTemplate, keyword),
			Description:    fmt.Sprintf(template.DescriptionTemplate, keyword),
			ImageURL:       helpers.RandomChoice(s.gen, imageURLs),
			CallToAction:   helpers.RandomChoice(s.gen, template.CTAs),
			LandingPageURL: fmt.Sprintf("https://www.example-%d.com/%s", advertiser.ID, s.gen.RandomSlug(3)),
			CreativeType:   "banner",
		}

		req := fixtures.BuildCampaignRequest(
			advertiser.ID,
			fmt.Sprintf("Competing Campaign %d", i+1),
			"ACTIVE",
			budget,
			bidAmount,
			budget*0.1,
			pricingModel,
			startDate,
			endDate,
			creative,
			fixtures.TargetingData{
				Keywords: sharedKeywords,
				Topics:   sharedTopics,
				Entities: sharedEntities,
			},
			sharedCountries,
			sharedDevices,
		)

		if s.dryRun {
			s.log("  [DRY RUN] Would create competing campaign %d for advertiser %d", i+1, advertiser.ID)
			continue
		}

		campaign, err := s.client.CreateCampaign(req)
		if err != nil {
			result.Failed++
			result.Errors = append(result.Errors, fmt.Errorf("failed to create competing campaign %d: %w", i+1, err))
			s.log("  ✗ Failed to create competing campaign %d - %v", i+1, err)
			continue
		}

		result.Campaigns = append(result.Campaigns, *campaign)
		s.log("  ✓ Created competing campaign %d (Campaign ID: %d, Ad ID: %d, Bid: $%.2f %s)",
			i+1, campaign.CampaignID, campaign.AdID, bidAmount, pricingModel)

		s.mu.Lock()
		s.campaigns = append(s.campaigns, *campaign)
		s.mu.Unlock()
	}

	s.log("Competing campaigns seeding complete: %d created, %d failed", len(result.Campaigns), result.Failed)
	return result, nil
}

type FileSeedResult struct {
	Total    int
	Created  int
	Failed   int
	Errors   []error
	Duration time.Duration
}

func (s *Seeder) SeedFromFile(ctx context.Context, filePath string, workers int, advIDMap map[int]int32) (*FileSeedResult, error) {
	start := time.Now()

	data, err := os.ReadFile(filePath)
	if err != nil {
		return nil, fmt.Errorf("failed to read file %s: %w", filePath, err)
	}

	var requests []client.CreateCampaignRequest
	if err := json.Unmarshal(data, &requests); err != nil {
		return nil, fmt.Errorf("failed to parse campaign requests: %w", err)
	}

	total := len(requests)
	fmt.Printf("Loaded %d campaign requests from %s\n", total, filePath)

	if s.dryRun {
		fmt.Printf("[DRY RUN] Would create %d campaigns with %d workers\n", total, workers)
		return &FileSeedResult{
			Total:    total,
			Duration: time.Since(start),
		}, nil
	}

	if workers < 1 {
		workers = 1
	}
	if workers > 50 {
		workers = 50
	}

	result := &FileSeedResult{
		Total:  total,
		Errors: make([]error, 0),
	}

	var (
		created int64
		failed  int64
		mu      sync.Mutex
	)

	jobs := make(chan int, workers*2)

	var wg sync.WaitGroup
	for w := 0; w < workers; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for idx := range jobs {
				select {
				case <-ctx.Done():
					return
				default:
				}

				req := requests[idx]
				if advIDMap != nil {
					if dbID, ok := advIDMap[int(req.AdvertiserID)]; ok {
						req.AdvertiserID = dbID
					}
				}
				_, err := s.client.CreateCampaign(req)
				if err != nil {
					atomic.AddInt64(&failed, 1)
					mu.Lock()
					if len(result.Errors) < 50 {
						result.Errors = append(result.Errors, fmt.Errorf("campaign %d (%s): %w", idx+1, req.Campaign.Name, err))
					}
					mu.Unlock()
				} else {
					atomic.AddInt64(&created, 1)
				}

				current := atomic.LoadInt64(&created) + atomic.LoadInt64(&failed)
				if current%100 == 0 {
					fmt.Printf("  Progress: %d/%d (created: %d, failed: %d)\n",
						current, total, atomic.LoadInt64(&created), atomic.LoadInt64(&failed))
				}
			}
		}()
	}

	for i := range requests {
		select {
		case <-ctx.Done():
			break
		case jobs <- i:
		}
	}
	close(jobs)

	wg.Wait()

	result.Created = int(atomic.LoadInt64(&created))
	result.Failed = int(atomic.LoadInt64(&failed))
	result.Duration = time.Since(start)

	fmt.Printf("\nFile seeding complete: %d created, %d failed (took %v)\n",
		result.Created, result.Failed, result.Duration.Round(time.Millisecond))

	return result, nil
}

func (s *Seeder) GetAdvertisers() []client.Advertiser {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.advertisers
}

func (s *Seeder) GetPublishers() []client.Publisher {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.publishers
}

func (s *Seeder) GetCampaigns() []client.CreateCampaignResponse {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.campaigns
}

func (s *Seeder) log(format string, args ...interface{}) {
	if s.verbose || s.dryRun {
		fmt.Printf(format+"\n", args...)
	}
}

func (s *Seeder) printSummary(result *SeedingResult) {
	fmt.Println("\n" + strings.Repeat("=", 50))
	fmt.Println("SEEDING COMPLETE - SUMMARY")
	fmt.Println(strings.Repeat("=", 50))
	fmt.Printf("Duration: %v\n\n", result.Duration)

	fmt.Println("Created Entities:")
	fmt.Printf("  ✓ Advertisers:          %d (failed: %d)\n", result.Stats.AdvertisersCreated, result.Stats.AdvertisersFailed)
	fmt.Printf("  ✓ Publishers:           %d (failed: %d)\n", result.Stats.PublishersCreated, result.Stats.PublishersFailed)
	fmt.Printf("  ✓ Campaigns:            %d (failed: %d)\n", result.Stats.CampaignsCreated, result.Stats.CampaignsFailed)
	fmt.Printf("  ✓ Competing Campaigns:  %d (failed: %d)\n", result.Stats.CompetingCampaignsCreated, result.Stats.CompetingCampaignsFailed)

	totalCreated := result.Stats.AdvertisersCreated + result.Stats.PublishersCreated + result.Stats.CampaignsCreated + result.Stats.CompetingCampaignsCreated
	totalFailed := result.Stats.AdvertisersFailed + result.Stats.PublishersFailed + result.Stats.CampaignsFailed + result.Stats.CompetingCampaignsFailed
	fmt.Printf("\nTotal: %d created, %d failed\n", totalCreated, totalFailed)

	if len(result.Errors) > 0 {
		fmt.Printf("\nErrors (%d):\n", len(result.Errors))
		for i, err := range result.Errors {
			if i >= 5 {
				fmt.Printf("  ... and %d more errors\n", len(result.Errors)-5)
				break
			}
			fmt.Printf("  - %v\n", err)
		}
	}

	fmt.Println(strings.Repeat("=", 50))
}
