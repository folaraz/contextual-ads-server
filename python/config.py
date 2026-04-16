"""
Centralized configuration for all Python services and consumers
"""

import os
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

class ConsumerType(Enum):
    """Types of consumers available"""
    AD = "ad"
    PAGE = "page"
    EVENT = "event"


class Topics:
    """Kafka topic constants """
    AD_ANALYZE = "ad_analyze"
    PAGE_ANALYZE = "page_analyze"
    AD_EVENT = "ad_event"
    PACING_EVENTS = "pacing_events"
    CONVERSION = "conversion"
    AUCTION = "auction"


class ConsumerGroups:
    """Consumer group constants"""
    AD_PROCESSOR = "ad_processor_group"
    PAGE_PROCESSOR = "page_processor_group"
    EVENT_AGGREGATOR = "event_aggregator_group"
    ANALYTICS = "analytics_consumer_group"


@dataclass
class RedisConfig:
    """Redis connection configuration"""
    host: str
    port: int
    db: int

    @classmethod
    def from_env(cls) -> 'RedisConfig':
        redis_host = os.getenv('REDIS_HOST', 'localhost')
        if redis_host == 'localhost' and os.getenv('KAFKA_BROKER'):
            redis_host = 'redis'

        return cls(
            host=redis_host,
            port=int(os.getenv('REDIS_PORT', '6379')),
            db=int(os.getenv('REDIS_DB', '0'))
        )


@dataclass
class PostgresConfig:
    """PostgreSQL connection configuration"""
    host: str
    port: int
    database: str
    user: str
    password: str
    min_conn: int = 10
    max_conn: int = 20

    @classmethod
    def from_env(cls) -> 'PostgresConfig':
        return cls(
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', '5435')),
            database=os.getenv('POSTGRES_DB', 'contextual_ads'),
            user=os.getenv('POSTGRES_USER', 'adsuser'),
            password=os.getenv('POSTGRES_PASSWORD', 'adspassword'),
            min_conn=int(os.getenv('PG_MIN_CONN', '10')),
            max_conn=int(os.getenv('PG_MAX_CONN', '20'))
        )


@dataclass
class KafkaConfig:
    """Kafka connection and consumer configuration"""
    bootstrap_servers: str
    group_id: str
    topics: List[str]
    auto_offset_reset: str = 'earliest'
    enable_auto_commit: bool = False
    max_retries: int = 3

    # Advanced settings
    max_poll_interval_ms: int = 300000
    session_timeout_ms: int = 45000
    heartbeat_interval_ms: int = 15000

    # Security settings (optional)
    security_protocol: Optional[str] = None
    sasl_mechanism: Optional[str] = None
    sasl_username: Optional[str] = None
    sasl_password: Optional[str] = None
    ssl_ca_location: Optional[str] = None

    @classmethod
    def from_env(
        cls,
        default_topics: List[str],
        default_group: str,
        topic_env_var: Optional[str] = None,
        group_env_var: Optional[str] = None
    ) -> 'KafkaConfig':
        """
        Create configuration from environment variables.

        Args:
            default_topics: Default topic list if env var not set
            default_group: Default consumer group if env var not set
            topic_env_var: Consumer-specific topic env var (e.g., 'AD_CONSUMER_TOPIC')
            group_env_var: Consumer-specific group env var (e.g., 'AD_CONSUMER_GROUP')
        """
        # Check consumer-specific env vars first, then fall back to generic ones
        topics_str = None
        if topic_env_var:
            topics_str = os.getenv(topic_env_var)
        if not topics_str:
            topics_str = os.getenv('KAFKA_TOPICS') or os.getenv('KAFKA_TOPIC')

        if topics_str:
            topics = [t.strip() for t in topics_str.split(',')]
        else:
            topics = default_topics

        # Check consumer-specific group env var first
        group_id = None
        if group_env_var:
            group_id = os.getenv(group_env_var)
        if not group_id:
            group_id = os.getenv('KAFKA_CONSUMER_GROUP', default_group)

        return cls(
            bootstrap_servers=os.getenv('KAFKA_BROKERS', 'localhost:9092'),
            group_id=group_id,
            topics=topics,
            auto_offset_reset=os.getenv('KAFKA_AUTO_OFFSET_RESET', 'earliest'),
            enable_auto_commit=os.getenv('KAFKA_AUTO_COMMIT', 'false').lower() == 'true',
            max_retries=int(os.getenv('KAFKA_MAX_RETRIES', '3')),
            max_poll_interval_ms=int(os.getenv('KAFKA_MAX_POLL_INTERVAL_MS', '300000')),
            session_timeout_ms=int(os.getenv('KAFKA_SESSION_TIMEOUT_MS', '45000')),
            heartbeat_interval_ms=int(os.getenv('KAFKA_HEARTBEAT_INTERVAL_MS', '15000')),
            security_protocol=os.getenv('KAFKA_SECURITY_PROTOCOL'),
            sasl_mechanism=os.getenv('KAFKA_SASL_MECHANISM'),
            sasl_username=os.getenv('KAFKA_SASL_USERNAME'),
            sasl_password=os.getenv('KAFKA_SASL_PASSWORD'),
            ssl_ca_location=os.getenv('KAFKA_SSL_CA_LOCATION'),
        )

    def to_consumer_config(self) -> dict:
        """Convert to confluent-kafka consumer configuration"""
        config = {
            'bootstrap.servers': self.bootstrap_servers,
            'group.id': self.group_id,
            'auto.offset.reset': self.auto_offset_reset,
            'enable.auto.commit': self.enable_auto_commit,
            'max.poll.interval.ms': self.max_poll_interval_ms,
            'session.timeout.ms': self.session_timeout_ms,
            'heartbeat.interval.ms': self.heartbeat_interval_ms,
        }

        if self.security_protocol:
            config['security.protocol'] = self.security_protocol
        if self.sasl_mechanism:
            config['sasl.mechanism'] = self.sasl_mechanism
        if self.sasl_username:
            config['sasl.username'] = self.sasl_username
        if self.sasl_password:
            config['sasl.password'] = self.sasl_password
        if self.ssl_ca_location:
            config['ssl.ca.location'] = self.ssl_ca_location

        return config


@dataclass
class CrawlerConfig:
    """Web crawler configuration"""
    user_agent: str
    headless: bool
    timeout: int
    max_retries: int
    cache_enabled: bool
    enable_crawler: bool = True
    auto_crawl: bool = True

    @classmethod
    def from_env(cls, prefix: str = '') -> 'CrawlerConfig':
        """
        Load crawler config from environment variables.

        Args:
            prefix: Optional prefix for env vars (e.g., 'AD_' or 'PAGE_')
                   This allows separate configs for ad and page consumers.
        """
        p = prefix.upper()
        return cls(
            enable_crawler=os.getenv(f'{p}ENABLE_CRAWLER', 'true').lower() == 'true',
            auto_crawl=os.getenv(f'{p}AUTO_CRAWL', os.getenv(f'{p}CRAWL_LANDING_PAGES', 'true')).lower() == 'true',
            user_agent=os.getenv(
                f'{p}CRAWLER_USER_AGENT',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            ),
            headless=os.getenv(f'{p}CRAWLER_HEADLESS', 'true').lower() == 'true',
            timeout=int(os.getenv(f'{p}CRAWLER_TIMEOUT', '30')),
            max_retries=int(os.getenv(f'{p}CRAWLER_MAX_RETRIES', '3')),
            cache_enabled=os.getenv(f'{p}CRAWLER_CACHE_ENABLED', 'true').lower() == 'true'
        )

    @classmethod
    def for_ad_consumer(cls) -> 'CrawlerConfig':
        """Get crawler config for ad consumer"""
        return cls.from_env(prefix='AD_')

    @classmethod
    def for_page_consumer(cls) -> 'CrawlerConfig':
        """Get crawler config for page consumer"""
        return cls.from_env(prefix='PAGE_')


@dataclass
class AggregationConfig:
    """Metrics aggregation configuration"""
    flush_interval_seconds: int = 10
    flush_threshold: int = 100

    @classmethod
    def from_env(cls) -> 'AggregationConfig':
        return cls(
            flush_interval_seconds=int(os.getenv('METRICS_FLUSH_INTERVAL_SECONDS', '10')),
            flush_threshold=int(os.getenv('METRICS_FLUSH_THRESHOLD', '100'))
        )



@dataclass
class SinkConfig:
    """Configuration for which sinks to enable"""
    postgres_enabled: bool = True
    redis_enabled: bool = True

    @classmethod
    def from_env(cls) -> 'SinkConfig':
        return cls(
            postgres_enabled=os.getenv('SINK_POSTGRES_ENABLED', 'true').lower() == 'true',
            redis_enabled=os.getenv('SINK_REDIS_ENABLED', 'true').lower() == 'true'
        )


@dataclass
class FlinkConfig:
    """Flink execution configuration"""
    parallelism: int = 1
    checkpoint_interval_ms: int = 60000
    checkpoint_dir: str = "file:///tmp/flink-checkpoints"
    window_size_seconds: int = 10

    @classmethod
    def from_env(cls) -> 'FlinkConfig':
        return cls(
            parallelism=int(os.getenv('FLINK_PARALLELISM', '1')),
            checkpoint_interval_ms=int(os.getenv('FLINK_CHECKPOINT_INTERVAL_MS', '60000')),
            checkpoint_dir=os.getenv('FLINK_CHECKPOINT_DIR', 'file:///tmp/flink-checkpoints'),
            window_size_seconds=int(os.getenv('FLINK_WINDOW_SIZE_SECONDS', '10'))
        )


@dataclass
class PacingConfig:
    """Pacing worker configuration"""
    interval_seconds: int = 30

    @classmethod
    def from_env(cls) -> 'PacingConfig':
        return cls(
            interval_seconds=int(os.getenv('PACING_INTERVAL_SECONDS', '30'))
        )


# =============================================================================
# Consumer-Specific Configuration Factories
# =============================================================================

class AdConsumerConfig:
    """Factory for Ad Consumer configuration"""

    @staticmethod
    def kafka_config() -> KafkaConfig:
        """Get Kafka config for ad consumer"""
        return KafkaConfig.from_env(
            default_topics=[Topics.AD_ANALYZE],
            default_group=ConsumerGroups.AD_PROCESSOR,
            topic_env_var='AD_CONSUMER_TOPIC',
            group_env_var='AD_CONSUMER_GROUP'
        )

    @staticmethod
    def crawler_config() -> CrawlerConfig:
        """Get crawler config for ad consumer"""
        return CrawlerConfig.for_ad_consumer()

    @staticmethod
    def all_configs() -> tuple:
        """Get all configs needed for ad consumer"""
        return (
            AdConsumerConfig.kafka_config(),
            PostgresConfig.from_env(),
            RedisConfig.from_env(),
            AdConsumerConfig.crawler_config(),
        )


class PageConsumerConfig:
    """Factory for Page Consumer configuration"""

    @staticmethod
    def kafka_config() -> KafkaConfig:
        """Get Kafka config for page consumer"""
        return KafkaConfig.from_env(
            default_topics=[Topics.PAGE_ANALYZE],
            default_group=ConsumerGroups.PAGE_PROCESSOR,
            topic_env_var='PAGE_CONSUMER_TOPIC',
            group_env_var='PAGE_CONSUMER_GROUP'
        )

    @staticmethod
    def crawler_config() -> CrawlerConfig:
        """Get crawler config for page consumer"""
        return CrawlerConfig.for_page_consumer()

    @staticmethod
    def all_configs() -> tuple:
        """Get all configs needed for page consumer"""
        return (
            PageConsumerConfig.kafka_config(),
            PostgresConfig.from_env(),
            RedisConfig.from_env(),
            PageConsumerConfig.crawler_config(),
        )


class ContextProcessorConfig:
    """Factory for unified Context Processor configuration (handles both ads and pages)"""

    @staticmethod
    def kafka_config() -> KafkaConfig:
        """Get Kafka config for context processor - subscribes to both ad and page topics"""
        return KafkaConfig.from_env(
            default_topics=[Topics.AD_ANALYZE, Topics.PAGE_ANALYZE],
            default_group="context_processor_group",
            topic_env_var='CONTEXT_PROCESSOR_TOPICS',
            group_env_var='CONTEXT_PROCESSOR_GROUP'
        )

    @staticmethod
    def crawler_config() -> CrawlerConfig:
        """Get crawler config for context processor"""
        return CrawlerConfig.for_page_consumer()  # Use page consumer settings (more permissive)

    @staticmethod
    def all_configs() -> tuple:
        """Get all configs needed for the context processor"""
        return (
            ContextProcessorConfig.kafka_config(),
            PostgresConfig.from_env(),
            RedisConfig.from_env(),
            ContextProcessorConfig.crawler_config(),
        )


class EventConsumerConfig:
    """Factory for Event Consumer (Flink) configuration"""

    @staticmethod
    def kafka_config() -> KafkaConfig:
        """Get Kafka config for event consumer"""
        return KafkaConfig.from_env(
            default_topics=[Topics.AD_EVENT],
            default_group=ConsumerGroups.EVENT_AGGREGATOR,
            topic_env_var='EVENT_CONSUMER_TOPICS',
            group_env_var='EVENT_CONSUMER_GROUP'
        )

    @staticmethod
    def all_configs() -> tuple:
        """Get all configs needed for event consumer"""
        return (
            FlinkConfig.from_env(),
            EventConsumerConfig.kafka_config(),
            PostgresConfig.from_env(),
            RedisConfig.from_env(),
            SinkConfig.from_env(),
        )

