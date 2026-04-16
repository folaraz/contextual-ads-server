package validation

import (
	"fmt"
	"strings"
	"sync"

	"github.com/folaraz/contextual-ads-server/internal/models"
	"github.com/go-playground/validator/v10"
)

var (
	validate *validator.Validate
	once     sync.Once
)

func initValidator() {
	validate = validator.New(validator.WithRequiredStructEnabled())

	_ = validate.RegisterValidation("pricing_model", validatePricingModel)
	_ = validate.RegisterValidation("status", validateStatus)
	_ = validate.RegisterValidation("creative_type", validateCreativeType)
}

func GetValidator() *validator.Validate {
	once.Do(initValidator)
	return validate
}

func Validate(s interface{}) error {
	once.Do(initValidator)
	return validate.Struct(s)
}

func validatePricingModel(fl validator.FieldLevel) bool {
	value := models.PricingModel(strings.ToUpper(fl.Field().String()))
	return value == "" || value.IsValid()
}

func validateStatus(fl validator.FieldLevel) bool {
	value := models.Status(strings.ToUpper(fl.Field().String()))
	return value == "" || value.IsValid()
}

func validateCreativeType(fl validator.FieldLevel) bool {
	value := models.CreativeType(strings.ToLower(fl.Field().String()))
	return value == "" || value.IsValid()
}

func FormatValidationError(fe validator.FieldError) string {
	field := fe.Field()
	switch fe.Tag() {
	case "required":
		return fmt.Sprintf("%s is required", field)
	case "email":
		return fmt.Sprintf("%s must be a valid email address", field)
	case "url":
		return fmt.Sprintf("%s must be a valid URL", field)
	case "min":
		return fmt.Sprintf("%s must be at least %s characters", field, fe.Param())
	case "max":
		return fmt.Sprintf("%s must be at most %s characters", field, fe.Param())
	case "gte":
		return fmt.Sprintf("%s must be greater than or equal to %s", field, fe.Param())
	case "lte":
		return fmt.Sprintf("%s must be less than or equal to %s", field, fe.Param())
	case "gt":
		return fmt.Sprintf("%s must be greater than %s", field, fe.Param())
	case "lt":
		return fmt.Sprintf("%s must be less than %s", field, fe.Param())
	case "oneof":
		return fmt.Sprintf("%s must be one of: %s", field, fe.Param())
	case "uuid":
		return fmt.Sprintf("%s must be a valid UUID", field)
	case "datetime":
		return fmt.Sprintf("%s must be a valid datetime", field)
	case "len":
		return fmt.Sprintf("%s must be exactly %s characters", field, fe.Param())
	case "gtfield":
		return fmt.Sprintf("%s must be after %s", field, fe.Param())
	case "pricing_model":
		return fmt.Sprintf("%s must be one of: CPC, CPM", field)
	case "status":
		return fmt.Sprintf("%s must be one of: ACTIVE, PAUSED, ARCHIVED, COMPLETED", field)
	case "creative_type":
		return fmt.Sprintf("%s must be one of: banner, native, video", field)
	default:
		return fmt.Sprintf("%s is invalid", field)
	}
}

func FormatValidationErrors(err error) []string {
	var messages []string
	if validationErrors, ok := err.(validator.ValidationErrors); ok {
		for _, e := range validationErrors {
			messages = append(messages, FormatValidationError(e))
		}
	}
	return messages
}
