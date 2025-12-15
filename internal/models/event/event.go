package event

type EventPayload struct {
	AdID        string `json:"adId"`
	EventType   string `json:"eventType"`
	Timestamp   int64  `json:"timestamp"`
	URL         string `json:"url"`
	ClickURL    string `json:"clickUrl"`
	PublisherID string `json:"publisherId"`
}
