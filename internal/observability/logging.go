package observability

import (
	"context"
	"io"
	"log/slog"
	"os"
	"runtime"
	"time"

	"go.opentelemetry.io/otel/exporters/otlp/otlplog/otlploggrpc"
	otellog "go.opentelemetry.io/otel/log"
	"go.opentelemetry.io/otel/log/global"
	sdklog "go.opentelemetry.io/otel/sdk/log"
	"go.opentelemetry.io/otel/sdk/resource"
)

var Logger *slog.Logger

var otelLogger otellog.Logger

var logProvider *sdklog.LoggerProvider

type LogConfig struct {
	Level     slog.Level
	Format    string // "json" or "text"
	Output    io.Writer
	AddSource bool
}

func DefaultLogConfig() LogConfig {
	level := slog.LevelInfo
	levelStr := os.Getenv("LOG_LEVEL")
	switch levelStr {
	case "debug", "DEBUG":
		level = slog.LevelDebug
	case "warn", "WARN", "warning", "WARNING":
		level = slog.LevelWarn
	case "error", "ERROR":
		level = slog.LevelError
	}

	format := "json"
	if os.Getenv("LOG_FORMAT") == "text" {
		format = "text"
	}

	return LogConfig{
		Level:     level,
		Format:    format,
		Output:    os.Stdout,
		AddSource: true,
	}
}

func InitLogger(cfg LogConfig) {
	opts := &slog.HandlerOptions{
		Level:     cfg.Level,
		AddSource: cfg.AddSource,
		ReplaceAttr: func(groups []string, a slog.Attr) slog.Attr {
			// Customize time format
			if a.Key == slog.TimeKey {
				return slog.String(slog.TimeKey, a.Value.Time().Format(time.RFC3339))
			}
			return a
		},
	}

	var handler slog.Handler
	if cfg.Format == "json" {
		handler = slog.NewJSONHandler(cfg.Output, opts)
	} else {
		handler = slog.NewTextHandler(cfg.Output, opts)
	}

	Logger = slog.New(handler)
	slog.SetDefault(Logger)
}

func InitLoggerWithOTel(ctx context.Context, res *resource.Resource) (func(context.Context) error, error) {
	endpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	if endpoint == "" {
		endpoint = "localhost:4317"
	}

	// Create OTLP log exporter
	exporter, err := otlploggrpc.New(ctx,
		otlploggrpc.WithEndpoint(endpoint),
		otlploggrpc.WithInsecure(),
	)
	if err != nil {
		return nil, err
	}

	// Create log provider
	logProvider = sdklog.NewLoggerProvider(
		sdklog.WithResource(res),
		sdklog.WithProcessor(sdklog.NewBatchProcessor(exporter)),
	)

	// Set global logger provider
	global.SetLoggerProvider(logProvider)

	// Get OTel logger
	otelLogger = logProvider.Logger(ServiceName)

	// Initialize slog with a handler that also sends to OTel
	cfg := DefaultLogConfig()
	opts := &slog.HandlerOptions{
		Level:     cfg.Level,
		AddSource: cfg.AddSource,
		ReplaceAttr: func(groups []string, a slog.Attr) slog.Attr {
			if a.Key == slog.TimeKey {
				return slog.String(slog.TimeKey, a.Value.Time().Format(time.RFC3339))
			}
			return a
		},
	}

	var baseHandler slog.Handler
	if cfg.Format == "json" {
		baseHandler = slog.NewJSONHandler(cfg.Output, opts)
	} else {
		baseHandler = slog.NewTextHandler(cfg.Output, opts)
	}

	// Wrap with OTel handler
	handler := &otelSlogHandler{
		baseHandler: baseHandler,
		otelLogger:  otelLogger,
		level:       cfg.Level,
	}

	Logger = slog.New(handler)
	slog.SetDefault(Logger)

	return logProvider.Shutdown, nil
}

type otelSlogHandler struct {
	baseHandler slog.Handler
	otelLogger  otellog.Logger
	level       slog.Level
	attrs       []slog.Attr
	groups      []string
}

func (h *otelSlogHandler) Enabled(ctx context.Context, level slog.Level) bool {
	return level >= h.level
}

func (h *otelSlogHandler) Handle(ctx context.Context, r slog.Record) error {
	// Send to stdout via base handler
	if err := h.baseHandler.Handle(ctx, r); err != nil {
		return err
	}

	// Send to OTel
	if h.otelLogger != nil {
		var record otellog.Record
		record.SetTimestamp(r.Time)
		record.SetBody(otellog.StringValue(r.Message))
		record.SetSeverity(slogLevelToOTel(r.Level))
		record.SetSeverityText(r.Level.String())

		// Add attributes
		var attrs []otellog.KeyValue
		r.Attrs(func(a slog.Attr) bool {
			attrs = append(attrs, slogAttrToOTel(a))
			return true
		})

		// Add pre-defined attrs from WithAttrs
		for _, a := range h.attrs {
			attrs = append(attrs, slogAttrToOTel(a))
		}

		record.AddAttributes(attrs...)

		h.otelLogger.Emit(ctx, record)
	}

	return nil
}

func (h *otelSlogHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	return &otelSlogHandler{
		baseHandler: h.baseHandler.WithAttrs(attrs),
		otelLogger:  h.otelLogger,
		level:       h.level,
		attrs:       append(h.attrs, attrs...),
		groups:      h.groups,
	}
}

func (h *otelSlogHandler) WithGroup(name string) slog.Handler {
	return &otelSlogHandler{
		baseHandler: h.baseHandler.WithGroup(name),
		otelLogger:  h.otelLogger,
		level:       h.level,
		attrs:       h.attrs,
		groups:      append(h.groups, name),
	}
}

func slogLevelToOTel(level slog.Level) otellog.Severity {
	switch {
	case level >= slog.LevelError:
		return otellog.SeverityError
	case level >= slog.LevelWarn:
		return otellog.SeverityWarn
	case level >= slog.LevelInfo:
		return otellog.SeverityInfo
	default:
		return otellog.SeverityDebug
	}
}

func slogAttrToOTel(attr slog.Attr) otellog.KeyValue {
	key := attr.Key
	val := attr.Value

	switch val.Kind() {
	case slog.KindString:
		return otellog.String(key, val.String())
	case slog.KindInt64:
		return otellog.Int64(key, val.Int64())
	case slog.KindFloat64:
		return otellog.Float64(key, val.Float64())
	case slog.KindBool:
		return otellog.Bool(key, val.Bool())
	case slog.KindTime:
		return otellog.String(key, val.Time().Format(time.RFC3339))
	case slog.KindDuration:
		return otellog.Int64(key, int64(val.Duration()))
	default:
		return otellog.String(key, val.String())
	}
}

func Info(ctx context.Context, msg string, args ...any) {
	Logger.InfoContext(ctx, msg, args...)
}

func Debug(ctx context.Context, msg string, args ...any) {
	Logger.DebugContext(ctx, msg, args...)
}

func Warn(ctx context.Context, msg string, args ...any) {
	Logger.WarnContext(ctx, msg, args...)
}

func Error(ctx context.Context, msg string, args ...any) {
	Logger.ErrorContext(ctx, msg, args...)
}

func LogAdServeRequest(ctx context.Context, publisherID, pageURL string, candidateCount int, filled bool,
	durationMs int64) {
	Logger.InfoContext(ctx, "ad_serve_request",
		"event", "ad_serve",
		"publisher_id", publisherID,
		"page_url", pageURL,
		"candidate_count", candidateCount,
		"filled", filled,
		"duration_ms", durationMs,
	)
}

func LogEvent(ctx context.Context, eventType, adID, publisherID, auctionID string, priceCents int64) {
	Logger.InfoContext(ctx, "event_tracked",
		"event", eventType,
		"ad_id", adID,
		"publisher_id", publisherID,
		"auction_id", auctionID,
		"price_cents", priceCents,
	)
}

func LogStartup(version, environment string, port int) {
	Logger.Info("application_starting",
		"event", "startup",
		"service", ServiceName,
		"version", version,
		"environment", environment,
		"port", port,
		"go_version", runtime.Version(),
		"num_cpu", runtime.NumCPU(),
	)
}

func LogShutdown(reason string) {
	Logger.Info("application_shutdown",
		"event", "shutdown",
		"service", ServiceName,
		"reason", reason,
	)
}
