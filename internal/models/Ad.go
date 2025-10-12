package models

type Ad struct {
	ID         string     `json:"id"`
	Advertiser Advertiser `json:"advertiser"`
	Campaign   Campaign   `json:"campaign"`
	Creative   Creative   `json:"creative"`
	Targeting  Targeting  `json:"targeting"`
}

type Advertiser struct {
	Name     string  `json:"name"`
	Domain   string  `json:"domain"`
	Budget   float64 `json:"budget"`
	Currency string  `json:"currency"`
}

type Campaign struct {
	Name   string  `json:"name"`
	Budget float64 `json:"budget"`
}

type Creative struct {
	Headline    string `json:"headline"`
	Description string `json:"description"`
	ImageURL    string `json:"image_url"`
}

type Targeting struct {
	Keywords []string `json:"keywords"`
	Topics   []string `json:"topics"`
	Entities []string `json:"entities"`
}
