package storage

type UrlContext struct {
	keywords map[string]int16
	vector   []float64
}

//hashing mechanism for urls

var cache = map[string]UrlContext{}

func GetContext(url string) UrlContext {
	if context, ok := cache[url]; ok {
		return context
	}
	return UrlContext{}
}

func set(url string, keywords map[string]int16, vector []float64) {
	var stuff UrlContext
	stuff.vector = vector
	stuff.keywords = keywords
	cache[url] = stuff
}
