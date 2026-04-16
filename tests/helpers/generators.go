package helpers

import (
	"math/rand"
	"strings"
	"time"
)

type Generator struct {
	rng *rand.Rand
}

func NewGenerator() *Generator {
	return &Generator{
		rng: rand.New(rand.NewSource(time.Now().UnixNano())),
	}
}

func (g *Generator) RandomInt(min, max int) int {
	if min >= max {
		return min
	}
	return g.rng.Intn(max-min+1) + min
}

func (g *Generator) RandomFloat(min, max float64) float64 {
	return min + g.rng.Float64()*(max-min)
}

func RandomChoice[T any](g *Generator, items []T) T {
	return items[g.rng.Intn(len(items))]
}

func RandomSample[T any](g *Generator, items []T, n int) []T {
	if n >= len(items) {
		return items
	}

	shuffled := make([]T, len(items))
	copy(shuffled, items)
	for i := len(shuffled) - 1; i > 0; i-- {
		j := g.rng.Intn(i + 1)
		shuffled[i], shuffled[j] = shuffled[j], shuffled[i]
	}

	return shuffled[:n]
}

func (g *Generator) RandomDateRange(minDurationDays, maxDurationDays int) (start, end time.Time) {
	start = time.Now().AddDate(0, 0, -g.RandomInt(0, 7))

	duration := g.RandomInt(minDurationDays, maxDurationDays)
	end = start.AddDate(0, 0, duration)

	return start, end
}

func FormatDate(t time.Time) string {
	return t.Format("2006-01-02")
}

func (g *Generator) RandomBudget(min, max float64) float64 {
	budget := g.RandomFloat(min, max)
	return float64(int(budget*100)) / 100
}

func (g *Generator) RandomBidAmount(pricingModel string, cpmRange, cpcRange [2]float64) float64 {
	var bid float64
	switch strings.ToUpper(pricingModel) {
	case "CPM":
		bid = g.RandomFloat(cpmRange[0], cpmRange[1])
	case "CPC":
		bid = g.RandomFloat(cpcRange[0], cpcRange[1])
	default:
		bid = g.RandomFloat(1.0, 5.0)
	}
	return float64(int(bid*100)) / 100
}

func (g *Generator) RandomUserAgent(deviceType string) string {
	switch deviceType {
	case "mobile":
		agents := []string{
			"Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
			"Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
			"Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/119.0.6045.169 Mobile/15E148 Safari/604.1",
		}
		return RandomChoice(g, agents)
	case "tablet":
		agents := []string{
			"Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
			"Mozilla/5.0 (Linux; Android 13; SM-X710) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
		}
		return RandomChoice(g, agents)
	default:
		agents := []string{
			"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
			"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
			"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
			"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
		}
		return RandomChoice(g, agents)
	}
}

func (g *Generator) RandomSlug(words int) string {
	wordList := []string{
		"best", "top", "new", "guide", "review", "tips", "how", "what", "why",
		"ultimate", "complete", "easy", "fast", "free", "amazing", "awesome",
		"2024", "2025", "today", "now", "quick", "simple", "full", "great",
	}
	selected := RandomSample(g, wordList, words)
	return strings.Join(selected, "-")
}
