package helpers

import (
	"fmt"
	"testing"
)

func AssertEqual[T comparable](t *testing.T, expected, actual T, msgAndArgs ...interface{}) {
	t.Helper()
	if expected != actual {
		msg := formatMessage("expected %v, got %v", expected, actual)
		if len(msgAndArgs) > 0 {
			msg = fmt.Sprintf("%s: %s", formatArgs(msgAndArgs...), msg)
		}
		t.Errorf(msg)
	}
}

func AssertTrue(t *testing.T, value bool, msgAndArgs ...interface{}) {
	t.Helper()
	if !value {
		msg := "expected true"
		if len(msgAndArgs) > 0 {
			msg = fmt.Sprintf("%s: %s", formatArgs(msgAndArgs...), msg)
		}
		t.Errorf(msg)
	}
}

func AssertGreater[T ~int | ~int32 | ~int64 | ~float64](t *testing.T, value, than T, msgAndArgs ...interface{}) {
	t.Helper()
	if value <= than {
		msg := formatMessage("expected %v > %v", value, than)
		if len(msgAndArgs) > 0 {
			msg = fmt.Sprintf("%s: %s", formatArgs(msgAndArgs...), msg)
		}
		t.Errorf(msg)
	}
}

func RequireNoError(t *testing.T, err error, msgAndArgs ...interface{}) {
	t.Helper()
	if err != nil {
		msg := formatMessage("unexpected error: %v", err)
		if len(msgAndArgs) > 0 {
			msg = fmt.Sprintf("%s: %s", formatArgs(msgAndArgs...), msg)
		}
		t.Fatalf(msg)
	}
}

func formatMessage(format string, args ...interface{}) string {
	return fmt.Sprintf(format, args...)
}

func formatArgs(args ...interface{}) string {
	if len(args) == 0 {
		return ""
	}
	if len(args) == 1 {
		return fmt.Sprint(args[0])
	}
	if format, ok := args[0].(string); ok {
		return fmt.Sprintf(format, args[1:]...)
	}
	return fmt.Sprint(args...)
}
