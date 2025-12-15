package request

type AdRequest struct {
	SlotID      string  `json:"slotId"`
	PublisherID string  `json:"publisherId"`
	Sizes       [][]int `json:"sizes"`
	Context     Context `json:"context"`
	Device      Device  `json:"device"`
	Meta        Meta    `json:"meta"`
}

type Context struct {
	URL         string   `json:"url"`
	Keywords    []string `json:"keywords"`
	Title       string   `json:"title"`
	Description string   `json:"description"`
}

type Device struct {
	Type      string `json:"type"`
	UserAgent string `json:"userAgent"`
	Language  string `json:"language"`
}

type Meta struct {
	Timestamp int64 `json:"timestamp"`
}
