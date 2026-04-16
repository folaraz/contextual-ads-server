"""
Consumer package for processing messages from Kafka

Each consumer has its own dedicated:
- Consumer group
- Topic subscription
- Processing logic

Available Consumers:
- ContextProcessorConsumer: Processes both ad_analyze and page_analyze
- AnalyticsConsumer: Processes impression/click streams (Flink-based)
"""

from .async_base import AsyncKafkaConsumerBase
from .context_processor import (
    ContextProcessorConsumer,
    AdContextProcessor,
    AdDatabaseWriter,
    PageContextProcessor,
    PageDatabaseWriter,
)

__all__ = [
    # Base
    'AsyncKafkaConsumerBase',
    'ContextProcessorConsumer',
    'AdContextProcessor',
    'AdDatabaseWriter',
    'PageContextProcessor',
    'PageDatabaseWriter',
]

