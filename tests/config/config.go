package config

import (
	"fmt"
	"os"
	"time"

	"gopkg.in/yaml.v3"
)

type Config struct {
	API      APIConfig      `yaml:"api"`
	Seeding  SeedingConfig  `yaml:"seeding"`
	Timeouts TimeoutConfig  `yaml:"timeouts"`
	Kafka    KafkaConfig    `yaml:"kafka"`
	Database DatabaseConfig `yaml:"database"`
}

type APIConfig struct {
	BaseURL string `yaml:"base_url"`
	Timeout int    `yaml:"timeout_seconds"`
}

type SeedingConfig struct {
	Advertisers AdvertiserSeedConfig `yaml:"advertisers"`
	Publishers  PublisherSeedConfig  `yaml:"publishers"`
	Campaigns   CampaignSeedConfig   `yaml:"campaigns"`
}

type AdvertiserSeedConfig struct {
	Count      int      `yaml:"count"`
	Industries []string `yaml:"industries"`
}

type PublisherSeedConfig struct {
	Count      int      `yaml:"count"`
	Categories []string `yaml:"categories"`
}

type CampaignSeedConfig struct {
	Count            int            `yaml:"count"`
	BudgetRange      BudgetRange    `yaml:"budget_range"`
	PricingModels    []string       `yaml:"pricing_models"`
	BidAmountRange   BidAmountRange `yaml:"bid_amount_range"`
	DailyBudgetPct   float64        `yaml:"daily_budget_pct"`
	Countries        []string       `yaml:"countries"`
	Devices          []string       `yaml:"devices"`
	DurationDays     DurationRange  `yaml:"duration_days"`
	CampaignStatuses []string       `yaml:"campaign_statuses"`
}

type BudgetRange struct {
	Min float64 `yaml:"min"`
	Max float64 `yaml:"max"`
}

type BidAmountRange struct {
	CPM BudgetRange `yaml:"cpm"`
	CPC BudgetRange `yaml:"cpc"`
}

type DurationRange struct {
	Min int `yaml:"min"`
	Max int `yaml:"max"`
}

type TimeoutConfig struct {
	APIRequest     time.Duration `yaml:"api_request"`
	AdProcessing   time.Duration `yaml:"ad_processing"`
	PageProcessing time.Duration `yaml:"page_processing"`
}

type KafkaConfig struct {
	Brokers []string `yaml:"brokers"`
	Topics  struct {
		AdAnalyze   string `yaml:"ad_analyze"`
		PageAnalyze string `yaml:"page_analyze"`
		AdEvent     string `yaml:"ad_event"`
		Auction     string `yaml:"auction"`
	} `yaml:"topics"`
}

type DatabaseConfig struct {
	Host     string `yaml:"host"`
	Port     int    `yaml:"port"`
	User     string `yaml:"user"`
	Password string `yaml:"password"`
	DBName   string `yaml:"db_name"`
}

func DefaultConfig() *Config {
	return &Config{
		API: APIConfig{
			BaseURL: "http://localhost:8090",
			Timeout: 30,
		},
		Seeding: SeedingConfig{
			Advertisers: AdvertiserSeedConfig{
				Count: 20,
				Industries: []string{
					"e-commerce", "saas", "entertainment", "education",
					"finance", "healthcare", "travel", "automotive",
					"food-beverage", "technology", "fashion", "sports",
				},
			},
			Publishers: PublisherSeedConfig{
				Count: 50,
				Categories: []string{
					"news", "blog", "e-commerce", "entertainment",
					"sports", "technology", "lifestyle", "finance",
					"health", "travel", "food", "automotive",
				},
			},
			Campaigns: CampaignSeedConfig{
				Count: 100,
				BudgetRange: BudgetRange{
					Min: 100,
					Max: 50000,
				},
				PricingModels: []string{"CPM", "CPC"},
				BidAmountRange: BidAmountRange{
					CPM: BudgetRange{Min: 1.0, Max: 15.0},
					CPC: BudgetRange{Min: 0.5, Max: 5.0},
				},
				DailyBudgetPct: 0.1,
				Countries:      []string{"US", "CA", "GB", "DE", "FR", "AU"},
				Devices:        []string{"mobile", "desktop", "tablet"},
				DurationDays: DurationRange{
					Min: 7,
					Max: 90,
				},
				CampaignStatuses: []string{"ACTIVE", "ACTIVE", "ACTIVE", "PAUSED"},
			},
		},
		Timeouts: TimeoutConfig{
			APIRequest:     30 * time.Second,
			AdProcessing:   5 * time.Second,
			PageProcessing: 10 * time.Second,
		},
		Kafka: KafkaConfig{
			Brokers: []string{"localhost:9092"},
			Topics: struct {
				AdAnalyze   string `yaml:"ad_analyze"`
				PageAnalyze string `yaml:"page_analyze"`
				AdEvent     string `yaml:"ad_event"`
				Auction     string `yaml:"auction"`
			}{
				AdAnalyze:   "ad_analyze",
				PageAnalyze: "page_analyze",
				AdEvent:     "ad_event",
				Auction:     "auction",
			},
		},
		Database: DatabaseConfig{
			Host:     "localhost",
			Port:     5435,
			User:     "adsuser",
			Password: "adspassword",
			DBName:   "contextual_ads",
		},
	}
}

func LoadConfig(path string) (*Config, error) {
	cfg := DefaultConfig()

	applyEnvOverrides := func(cfg *Config) {
		if apiURL := os.Getenv("TEST_API_URL"); apiURL != "" {
			cfg.API.BaseURL = apiURL
		}
	}

	if path == "" {
		candidates := []string{
			"tests/config/config.yaml",
			"tests/config/config.yml",
		}
		for _, candidate := range candidates {
			if _, err := os.Stat(candidate); err == nil {
				path = candidate
				break
			}
		}
		if path == "" {
			applyEnvOverrides(cfg)
			return cfg, nil
		}
	}

	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			applyEnvOverrides(cfg)
			return cfg, nil
		}
		return nil, fmt.Errorf("failed to read config file: %w", err)
	}

	if err := yaml.Unmarshal(data, cfg); err != nil {
		return nil, fmt.Errorf("failed to parse config file: %w", err)
	}

	applyEnvOverrides(cfg)

	return cfg, nil
}

func (c *DatabaseConfig) DSN() string {
	return fmt.Sprintf("postgresql://%s:%s@%s:%d/%s?sslmode=disable",
		c.User, c.Password, c.Host, c.Port, c.DBName)
}
