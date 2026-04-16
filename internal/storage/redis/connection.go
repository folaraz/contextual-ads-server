package redis

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"

	goredis "github.com/redis/go-redis/v9"
)

var (
	client *goredis.Client
	once   sync.Once
	mu     sync.RWMutex
)

func InitClient(cfg *Config) error {
	var initErr error

	once.Do(func() {
		client = goredis.NewClient(&goredis.Options{
			Addr:            cfg.Addr,
			Password:        cfg.Password,
			DB:              cfg.DB,
			MaxRetries:      cfg.MaxRetries,
			DialTimeout:     cfg.DialTimeout,
			ReadTimeout:     cfg.ReadTimeout,
			WriteTimeout:    cfg.WriteTimeout,
			PoolSize:        cfg.PoolSize,
			MinIdleConns:    cfg.MinIdleConns,
			PoolTimeout:     cfg.PoolTimeout,
			ConnMaxIdleTime: cfg.IdleTimeout,
			Protocol:        2,
		})

		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()

		if err := client.Ping(ctx).Err(); err != nil {
			initErr = fmt.Errorf("failed to connect to Redis at %s: %w", cfg.Addr, err)
			log.Printf("Warning: %v", initErr)
			return
		}

		// Get Redis info
		info, err := client.Info(ctx, "server").Result()
		if err == nil {
			log.Printf("Redis connection established successfully at %s", cfg.Addr)
			if len(info) > 0 {
				log.Printf("   Redis server info available")
			}
		} else {
			log.Printf("Redis connection established at %s (info not available)", cfg.Addr)
		}
	})

	return initErr
}

func GetRedisClient() *goredis.Client {
	mu.RLock()
	if client != nil {
		mu.RUnlock()
		return client
	}
	mu.RUnlock()

	mu.Lock()
	defer mu.Unlock()

	if client != nil {
		return client
	}

	// Initialize with default config
	if err := InitClient(DefaultConfig()); err != nil {
		log.Printf("Warning: Redis initialization failed: %v", err)
		log.Println("Warning: Returning a new Redis client instance (may fail on operations)")
		return goredis.NewClient(&goredis.Options{
			Addr:     "localhost:6379",
			Protocol: 2,
		})
	}

	return client
}
