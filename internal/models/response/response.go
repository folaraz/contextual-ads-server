package response

type AdResponse struct {
	AdID        string `json:"adId"`
	PublisherID string `json:"publisherId"`
	Type        string `json:"type"`
	Creative    string `json:"creative"`
	ClickURL    string `json:"clickUrl"`
}
