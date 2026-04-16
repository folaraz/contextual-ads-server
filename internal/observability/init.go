package observability

import (
	"context"
	"os"

	"go.opentelemetry.io/otel/sdk/resource"
	semconv "go.opentelemetry.io/otel/semconv/v1.24.0"
)

const (
	ServiceName    = "contextual-ads-server"
	ServiceVersion = "1.0.0"
)

type ShutdownFunc func(context.Context) error

type Observability struct {
	serviceName   string
	shutdownFuncs []ShutdownFunc
}

func NewObservability(serviceName string) *Observability {
	obs := &Observability{
		serviceName:   serviceName,
		shutdownFuncs: make([]ShutdownFunc, 0),
	}

	ctx := context.Background()

	// Create shared resource for metrics and logs
	res, err := createResource()
	if err != nil {
		// Can't use Logger yet, use stdlib log
		InitLogger(DefaultLogConfig())
		Logger.Warn("Failed to create resource", "error", err)
	}

	// Initialize OTel logging (also initializes slog for stdout)
	if res != nil {
		logShutdown, err := InitLoggerWithOTel(ctx, res)
		if err != nil {
			// Fall back to stdout-only logging
			InitLogger(DefaultLogConfig())
			Logger.Warn("Failed to initialize OTel logging, using stdout only", "error", err)
		} else {
			obs.shutdownFuncs = append(obs.shutdownFuncs, logShutdown)
			Logger.Info("OTel logging initialized successfully",
				"endpoint", getEnv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317"))
		}
	} else {
		InitLogger(DefaultLogConfig())
	}

	// Initialize metrics
	if res != nil {
		metricsShutdown, err := InitMetrics(ctx, res)
		if err != nil {
			Logger.Warn("Failed to initialize metrics", "error", err)
		} else {
			obs.shutdownFuncs = append(obs.shutdownFuncs, metricsShutdown)
			Logger.Info("Metrics initialized successfully",
				"endpoint", getEnv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317"))
		}
	}

	// Initialize tracing
	if res != nil {
		tracingShutdown, err := InitTracing(ctx, res)
		if err != nil {
			Logger.Warn("Failed to initialize tracing", "error", err)
		} else {
			obs.shutdownFuncs = append(obs.shutdownFuncs, tracingShutdown)
			Logger.Info("Tracing initialized successfully",
				"endpoint", getEnv("OTEL_EXPORTER_OTLP_ENDPOINT", "localhost:4317"))
		}
	}

	// Log startup
	LogStartup(ServiceVersion, getEnv("ENVIRONMENT", "development"), 8090)

	return obs
}

func InitObservability(ctx context.Context) (*Observability, error) {
	return NewObservability(ServiceName), nil
}

func (o *Observability) Shutdown(ctx context.Context) error {
	var lastErr error
	for _, shutdown := range o.shutdownFuncs {
		if err := shutdown(ctx); err != nil {
			Logger.Error("Error shutting down observability component", "error", err)
			lastErr = err
		}
	}
	LogShutdown("graceful")
	return lastErr
}

func (o *Observability) Info(msg string, args ...any) {
	Logger.Info(msg, args...)
}

func (o *Observability) Error(err error, msg string, args ...any) {
	allArgs := append([]any{"error", err}, args...)
	Logger.Error(msg, allArgs...)
}

func (o *Observability) Fatal(err error, msg string, args ...any) {
	allArgs := append([]any{"error", err}, args...)
	Logger.Error(msg, allArgs...)
	os.Exit(1)
}

func createResource() (*resource.Resource, error) {
	return resource.Merge(
		resource.Default(),
		resource.NewWithAttributes(
			semconv.SchemaURL,
			semconv.ServiceName(ServiceName),
			semconv.ServiceVersion(ServiceVersion),
			semconv.ServiceNamespace("contextual-ads"),
			semconv.DeploymentEnvironment(getEnv("ENVIRONMENT", "development")),
			semconv.HostName(getHostname()),
		),
	)
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getHostname() string {
	hostname, err := os.Hostname()
	if err != nil {
		return "unknown"
	}
	return hostname
}
