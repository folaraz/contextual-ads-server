package utils

import (
	"crypto/sha256"
	"encoding/hex"
	"net/url"
	"strings"
)

func CanonicalURL(raw string) (string, error) {
	u, err := url.Parse(raw)
	if err != nil {
		return "", err
	}
	u.Scheme = strings.ToLower(u.Scheme)
	u.Host = strings.ToLower(u.Host)
	u.Path = strings.TrimRight(u.Path, "/")
	return u.String(), nil
}

func GenerateHashAndURL(raw string) (string, error) {
	norm, err := CanonicalURL(raw)
	if err != nil {
		return "", err
	}
	hash := sha256.Sum256([]byte(norm))
	return hex.EncodeToString(hash[:]), nil
}
