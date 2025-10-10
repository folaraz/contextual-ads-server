package utils

import (
	"crypto/sha256"
	"encoding/hex"

	"github.com/PuerkitoBio/purell"
)

func GenerateHashAndURL(rawURL string) (string, string, error) {
	flags := purell.FlagsUsuallySafeGreedy | purell.FlagRemoveFragment

	canonicalURL, err := purell.NormalizeURLString(rawURL, flags)
	if err != nil {
		return "", "", err
	}

	hash := sha256.Sum256([]byte(canonicalURL))
	urlHash := hex.EncodeToString(hash[:])
	return urlHash, canonicalURL, nil
}
