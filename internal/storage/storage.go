package storage

import (
	"context"
	"fmt"

	"github.com/folaraz/contextual-ads-server/internal/retrieval"
	"github.com/redis/go-redis/v9"
)

type PageContext struct {
	Keywords  []string
	Entities  []string
	Topics    []string
	Embedding []float64
}

func GetContext(urlHash string) PageContext {
	ctx := context.Background()
	client := GetRedisClient()
	var pageContext PageContext
	err := client.HGetAll(ctx, "page:"+urlHash).Scan(&pageContext)
	if err != nil {
		panic(err)
	}
	return pageContext
}

func QueryAds(pageContext PageContext) []retrieval.Ad {
	client := GetRedisClient()
	ctx := context.Background()

	results, err := client.FTSearchWithArgs(ctx,
		"vector_idx",
		"*=>[KNN 3 @embedding $vec AS vector_distance]",
		&redis.FTSearchOptions{
			Return: []redis.FTSearchReturn{
				{FieldName: "vector_distance"},
				{FieldName: "content"},
			},
			DialectVersion: 2,
			Params: map[string]any{
				"vec": buffer,
			},
		},
	).Result()

	for _, doc := range results.Docs {
		fmt.Printf(
			"ID: %v, Distance:%v, Content:'%v'\n",
			doc.ID, doc.Fields["vector_distance"], doc.Fields["content"],
		)
	}
}
