package handlers

import (
	"encoding/json"
	"net/http"

	"github.com/folaraz/contextual-ads-server/internal/validation"
)

type ValidationError struct {
	Field   string `json:"field"`
	Message string `json:"message"`
}

func ValidateStruct(s interface{}) []ValidationError {
	var errors []ValidationError

	err := validation.Validate(s)
	if err != nil {
		messages := validation.FormatValidationErrors(err)
		for _, msg := range messages {
			errors = append(errors, ValidationError{
				Field:   "",
				Message: msg,
			})
		}
	}

	return errors
}

func writeJSONError(w http.ResponseWriter, statusCode int, message string, err error) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)

	response := map[string]interface{}{
		"success": false,
		"error":   message,
	}

	if err != nil {
		response["details"] = err.Error()
	}

	_ = json.NewEncoder(w).Encode(response)
}

func writeValidationErrors(w http.ResponseWriter, errors []ValidationError) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusBadRequest)

	response := map[string]interface{}{
		"success": false,
		"error":   "Validation failed",
		"details": errors,
	}

	_ = json.NewEncoder(w).Encode(response)
}
