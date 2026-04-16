package redis

import (
	"fmt"
	"time"

	"github.com/folaraz/contextual-ads-server/internal/utils"
)

type Config struct {
	Addr         string
	Password     string
	DB           int
	MaxRetries   int
	PoolSize     int
	MinIdleConns int
	DialTimeout  time.Duration
	ReadTimeout  time.Duration
	WriteTimeout time.Duration
	PoolTimeout  time.Duration
	IdleTimeout  time.Duration
}

func DefaultConfig() *Config {
	return &Config{
		Addr:         utils.GetEnv("REDIS_ADDR", "localhost:6379"),
		Password:     utils.GetEnv("REDIS_PASSWORD", ""),
		DB:           utils.GetEnvAsInt("REDIS_DB", 0),
		MaxRetries:   utils.GetEnvAsInt("REDIS_MAX_RETRIES", 3),
		PoolSize:     utils.GetEnvAsInt("REDIS_POOL_SIZE", 30),
		MinIdleConns: utils.GetEnvAsInt("REDIS_MIN_IDLE_CONNS", 10),
		DialTimeout:  utils.GetEnvDuration("REDIS_DIAL_TIMEOUT", 5*time.Second),
		ReadTimeout:  utils.GetEnvDuration("REDIS_READ_TIMEOUT", 3*time.Second),
		WriteTimeout: utils.GetEnvDuration("REDIS_WRITE_TIMEOUT", 3*time.Second),
		PoolTimeout:  utils.GetEnvDuration("REDIS_POOL_TIMEOUT", 4*time.Second),
		IdleTimeout:  utils.GetEnvDuration("REDIS_IDLE_TIMEOUT", 5*time.Minute),
	}
}

func (c *Config) ConnectionURL() string {
	if c.Password != "" {
		return fmt.Sprintf("redis://:%s@%s/%d", c.Password, c.Addr, c.DB)
	}
	return fmt.Sprintf("redis://%s/%d", c.Addr, c.DB)
}
