package publisher

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/folaraz/contextual-ads-server/internal/observability"
	"github.com/segmentio/kafka-go"
)

const (
	DefaultKafkaTimeout    = 10 * time.Second
	DefaultKafkaMaxRetries = 3
	DefaultBatchSize       = 100
	DefaultBatchTimeout    = 100 * time.Millisecond
	DefaultRequiredAcks    = kafka.RequireAll
)

type KafkaConfig struct {
	Brokers      []string
	MaxRetries   int
	Timeout      time.Duration
	BatchSize    int
	BatchTimeout time.Duration
	RequiredAcks kafka.RequiredAcks
	Compression  kafka.Compression
	Async        bool
}

func DefaultKafkaConfig() KafkaConfig {
	brokers := os.Getenv("KAFKA_BROKERS")
	if brokers == "" {
		brokers = "localhost:9092"
	}

	return KafkaConfig{
		Brokers:      strings.Split(brokers, ","),
		MaxRetries:   DefaultKafkaMaxRetries,
		Timeout:      DefaultKafkaTimeout,
		BatchSize:    DefaultBatchSize,
		BatchTimeout: DefaultBatchTimeout,
		RequiredAcks: DefaultRequiredAcks,
		Compression:  kafka.Snappy,
		Async:        false,
	}
}

type KafkaPublisher struct {
	config  KafkaConfig
	writers map[StreamType]*kafka.Writer
	mu      sync.RWMutex
}

func NewKafkaPublisher() *KafkaPublisher {
	cfg := DefaultKafkaConfig()
	return &KafkaPublisher{
		config:  cfg,
		writers: make(map[StreamType]*kafka.Writer),
	}
}

func (p *KafkaPublisher) getWriter(streamType StreamType) *kafka.Writer {
	p.mu.RLock()
	writer, exists := p.writers[streamType]
	p.mu.RUnlock()

	if exists {
		return writer
	}

	p.mu.Lock()
	defer p.mu.Unlock()

	if writer, exists := p.writers[streamType]; exists {
		return writer
	}

	writer = &kafka.Writer{
		Addr:         kafka.TCP(p.config.Brokers...),
		Topic:        streamType.String(),
		Balancer:     &kafka.LeastBytes{},
		BatchSize:    p.config.BatchSize,
		BatchTimeout: p.config.BatchTimeout,
		RequiredAcks: p.config.RequiredAcks,
		Compression:  p.config.Compression,
		Async:        p.config.Async,
		MaxAttempts:  p.config.MaxRetries,
		WriteTimeout: p.config.Timeout,
	}

	p.writers[streamType] = writer
	observability.Info(context.Background(), "Kafka writer created", "topic", streamType.String())

	return writer
}

func (p *KafkaPublisher) Publish(msg Message) error {
	streamType := msg.GetStreamType()
	if !streamType.IsValid() {
		return fmt.Errorf("invalid stream type: %s", streamType)
	}

	writer := p.getWriter(streamType)
	topic := streamType.String()

	// Serialize message to JSON
	value, err := json.Marshal(msg.ToMap())
	if err != nil {
		return fmt.Errorf("failed to serialize message: %w", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), p.config.Timeout)
	defer cancel()

	kafkaMsg := kafka.Message{
		Value: value,
		Time:  time.Now(),
	}

	// Add key for partitioning if available
	if keyable, ok := msg.(Keyable); ok {
		kafkaMsg.Key = []byte(keyable.GetKey())
	}

	start := time.Now()
	err = writer.WriteMessages(ctx, kafkaMsg)
	duration := time.Since(start)

	observability.RecordKafkaPublish(ctx, topic, err == nil, duration)

	if err != nil {
		observability.Error(ctx, "Kafka publish failed", "topic", topic, "error", err, "duration_ms", duration.Milliseconds())
		return fmt.Errorf("failed to publish to topic %s: %w", streamType, err)
	}

	observability.Debug(ctx, "Kafka publish success", "topic", topic, "duration_ms", duration.Milliseconds())
	return nil
}

func (p *KafkaPublisher) PublishAsync(msg Message) <-chan error {
	errChan := make(chan error, 1)

	go func() {
		defer close(errChan)
		err := p.Publish(msg)
		if err != nil {
			observability.Error(context.Background(), "Kafka async publish failed",
				"topic", msg.GetStreamType().String(), "error", err)
			errChan <- err
		}
	}()

	return errChan
}

func (p *KafkaPublisher) Close() error {
	p.mu.Lock()
	defer p.mu.Unlock()

	var lastErr error
	for streamType, writer := range p.writers {
		if err := writer.Close(); err != nil {
			observability.Error(context.Background(), "Failed to close Kafka writer",
				"topic", streamType.String(), "error", err)
			lastErr = err
		}
	}

	p.writers = make(map[StreamType]*kafka.Writer)
	observability.Info(context.Background(), "All Kafka writers closed")

	return lastErr
}

type Keyable interface {
	GetKey() string
}
