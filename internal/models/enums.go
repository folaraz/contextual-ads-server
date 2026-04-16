package models

type PricingModel string

const (
	PricingModelCPC PricingModel = "CPC"
	PricingModelCPM PricingModel = "CPM"
)

func (p PricingModel) IsValid() bool {
	switch p {
	case PricingModelCPC, PricingModelCPM:
		return true
	}
	return false
}

func (p PricingModel) String() string {
	return string(p)
}

type Status string

const (
	StatusActive          Status = "ACTIVE"
	StatusPaused          Status = "PAUSED"
	StatusArchived        Status = "ARCHIVED"
	StatusCompleted       Status = "COMPLETED"
	StatusPendingAnalysis Status = "PENDING_ANALYSIS"
)

func (s Status) IsValid() bool {
	switch s {
	case StatusActive, StatusPaused, StatusArchived, StatusCompleted, StatusPendingAnalysis:
		return true
	}
	return false
}

func (s Status) String() string {
	return string(s)
}

type CreativeType string

const (
	CreativeTypeBanner CreativeType = "banner"
	CreativeTypeNative CreativeType = "native"
	CreativeTypeVideo  CreativeType = "video"
)

func (c CreativeType) IsValid() bool {
	switch c {
	case CreativeTypeBanner, CreativeTypeNative, CreativeTypeVideo:
		return true
	}
	return false
}

func (c CreativeType) String() string {
	return string(c)
}
