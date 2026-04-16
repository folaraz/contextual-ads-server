package utils

import (
	"crypto/sha256"
	"encoding/hex"
	"net/url"
	"strings"
)

func GenerateHashAndURL(raw string) (string, error) {
	norm, err := canonicalURL(raw)
	if err != nil {
		return "", err
	}
	hash := sha256.Sum256([]byte(norm))
	return hex.EncodeToString(hash[:]), nil
}

func canonicalURL(raw string) (string, error) {
	for _, scheme := range []string{"https://", "http://"} {
		for strings.HasPrefix(raw, scheme+scheme) {
			raw = strings.TrimPrefix(raw, scheme)
		}
	}

	u, err := url.Parse(raw)
	if err != nil {
		return "", err
	}
	u.Scheme = strings.ToLower(u.Scheme)
	u.Host = strings.ToLower(u.Host)
	u.Path = strings.TrimRight(u.Path, "/")
	return u.String(), nil
}
