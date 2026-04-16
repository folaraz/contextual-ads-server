package fixtures

import (
	"encoding/json"
	"os"
	"path/filepath"
	"runtime"

	"github.com/folaraz/contextual-ads-server/internal/cache"
)

func LoadTaxonomyMapping() (cache.TaxonomyMapping, error) {
	dataDir := findDataDir()

	productToContent, err := loadJSONMap(filepath.Join(dataDir, "ad_product_to_content_taxonomy_mapping.json"))
	if err != nil {
		return cache.TaxonomyMapping{}, err
	}

	contentToProduct, err := loadJSONMap(filepath.Join(dataDir, "content_to_ad_product_taxonomy_mapping.json"))
	if err != nil {
		return cache.TaxonomyMapping{}, err
	}

	return cache.TaxonomyMapping{
		ProductToContent: productToContent,
		ContentToProduct: contentToProduct,
	}, nil
}

func loadJSONMap(path string) (map[string]string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var m map[string]string
	if err := json.Unmarshal(data, &m); err != nil {
		return nil, err
	}
	return m, nil
}

func findDataDir() string {
	_, filename, _, _ := runtime.Caller(0)
	projectRoot := filepath.Join(filepath.Dir(filename), "..", "..", "..")
	return filepath.Join(projectRoot, "data")
}
