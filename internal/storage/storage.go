package storage

type UrlContext struct {
	Keywords        []string
	NamedEntities   []string
	EmbeddingVector []float64
	IabCategories   []string
}

//hashing mechanism for urls

var cache = map[string]UrlContext{}

func GetContext(urlHash string) UrlContext {
	if context, ok := cache[urlHash]; ok {
		return context
	}
	return UrlContext{}
}

func set(url string, keywords map[string]int16, vector []float64) {
	var stuff UrlContext
	stuff.vector = vector
	stuff.Keywords = keywords
	cache[url] = stuff
}
