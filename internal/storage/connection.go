package storage

import (
	"github.com/redis/go-redis/v9"
)

func GetRedisClient() *redis.Client {
	client := redis.NewClient(&redis.Options{
		Addr:     "localhost:6379",
		Protocol: 3,
	})
	return client
}
