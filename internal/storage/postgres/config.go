package postgres

import (
	"fmt"
	"time"

	"github.com/folaraz/contextual-ads-server/internal/utils"
)

type Config struct {
	Host            string
	Port            int
	Database        string
	Username        string
	Password        string
	SSLMode         string
	MaxOpenConns    int
	MaxIdleConns    int
	ConnMaxLifetime time.Duration
	ConnMaxIdleTime time.Duration
}

func DefaultConfig() *Config {
	return &Config{
		Host:            utils.GetEnv("DB_HOST", "localhost"),
		Port:            utils.GetEnvAsInt("DB_PORT", 5435),
		Database:        utils.GetEnv("DB_NAME", "contextual_ads"),
		Username:        utils.GetEnv("DB_USER", "adsuser"),
		Password:        utils.GetEnv("DB_PASSWORD", "adspassword"),
		SSLMode:         utils.GetEnv("DB_SSL_MODE", "disable"),
		MaxOpenConns:    utils.GetEnvAsInt("DB_MAX_OPEN_CONNS", 25),
		MaxIdleConns:    utils.GetEnvAsInt("DB_MAX_IDLE_CONNS", 5),
		ConnMaxLifetime: time.Duration(utils.GetEnvAsInt("DB_CONN_MAX_LIFETIME_MINUTES", 30)) * time.Minute,
		ConnMaxIdleTime: time.Duration(utils.GetEnvAsInt("DB_CONN_MAX_IDLE_TIME_MINUTES", 5)) * time.Minute,
	}
}

func (c *Config) DSN() string {
	return fmt.Sprintf(
		"host=%s port=%d user=%s password=%s dbname=%s sslmode=%s",
		c.Host, c.Port, c.Username, c.Password, c.Database, c.SSLMode,
	)
}

func (c *Config) ConnectionURL() string {
	return fmt.Sprintf(
		"postgres://%s:%s@%s:%d/%s?sslmode=%s",
		c.Username, c.Password, c.Host, c.Port, c.Database, c.SSLMode,
	)
}
