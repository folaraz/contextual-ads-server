package retrieval

import "github.com/folaraz/contextual-ads-server/internal/storage"

type Ad struct {
	ID       string   `json:"id"`
	Title    string   `json:"title"`
	Url      string   `json:"url"`
	Keywords []string `json:"keywords"`
	Bid      float64  `json:"bid"`
}

func RetrieveAd(ctx storage.UrlContext) []Ad {
	keywords := ctx.Keywords
	namedEntities := ctx.NamedEntities
	iabCategories := ctx.IabCategories
	embeddingVector := ctx.EmbeddingVector

	return []Ad{}
}
