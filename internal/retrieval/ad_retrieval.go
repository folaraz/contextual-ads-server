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

//todo: redis cache for ads kw:tag -> [ad1, ad2, ad3]
//todo: redis cache for ner ner:tag -> [ad1, ad2, ad3]
//todo: redis cache for iab iab:tag -> [ad1, ad2, ad3]
//todo: redis cache for ad -> {id, title, url, keywords, bid, embedding}
//todo: redis cache for urlhash -> {id, title, url, keywords, bid, embedding}
//perofrm consine similarity on the url embedding vector and the embedding vector of the ad
