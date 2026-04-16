

import asyncio
import json
import os
import sys
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

sys.path.insert(0, '..')

from config import KafkaConfig
from confluent_kafka import Consumer, KafkaException

from observability import (
    init_observability,
    get_structured_logger,
    get_metrics_manager,
    record_message_processed,
    record_message_failed,
    record_processing_duration,
    start_span,
    add_span_attributes,
    record_exception,
)


class AsyncKafkaConsumerBase(ABC):
    """
    Async base class for Kafka consumers with concurrent message processing.

    Subclasses must be implemented:
    - process_message_async(topic, key, value): Process a single message (async)
    - _init_components(): Initialize consumer-specific components
    """

    def __init__(self, kafka_config: KafkaConfig, consumer_name: str = "kafka_consumer",
                 max_concurrency: int = 0):

        self.kafka_config = kafka_config
        self.consumer_name = consumer_name
        self.consumer: Optional[Consumer] = None
        self.running = False
        self._messages_processed = 0
        self._messages_failed = 0

        if max_concurrency <= 0:
            max_concurrency = int(os.getenv('MAX_CONCURRENCY', str(os.cpu_count() * 2 or 4)))
        self._max_concurrency = max_concurrency

        self._thread_pool = ThreadPoolExecutor(
            max_workers=int(os.getenv('NLP_THREAD_POOL_SIZE', '4'))
        )

        # Initialize observability
        init_observability(consumer_name, version="1.0.0")
        self.log = get_structured_logger(consumer_name)
        self.metrics = get_metrics_manager(consumer_name)

    def _init_kafka_consumer(self):
        """Initialize Kafka consumer"""
        try:
            config = self.kafka_config.to_consumer_config()
            self.consumer = Consumer(config)
            self.consumer.subscribe(self.kafka_config.topics)
            self.log.info(
                "Kafka consumer initialized",
                topics=self.kafka_config.topics,
                group_id=self.kafka_config.group_id
            )
        except KafkaException as e:
            self.log.error("Failed to initialize Kafka consumer", error=str(e))
            raise

    @abstractmethod
    def _init_components(self):
        """Initialize consumer-specific components (DB pools, processors, etc.)"""
        pass

    @abstractmethod
    async def process_message_async(self, topic: str, key: Optional[str],
                                     value: Dict[str, Any]) -> bool:
        """
        Process a single message from Kafka (async).

        Args:
            topic: The Kafka topic the message came from
            key: Message key (maybe None)
            value: Deserialized message value (JSON parsed to dict)

        Returns:
            True if processing succeeded, False otherwise
        """
        pass

    async def run_in_thread(self, func, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._thread_pool, func, *args)

    async def _handle_message_async(self, msg) -> bool:
        topic = msg.topic()
        key = msg.key().decode('utf-8') if msg.key() else None
        start_time = time.time()

        with start_span("handle_message", {"kafka.topic": topic, "kafka.partition": msg.partition()}):
            try:
                value = json.loads(msg.value().decode('utf-8'))
            except json.JSONDecodeError as e:
                self.log.error("Failed to parse message JSON", error=str(e), topic=topic)
                self._messages_failed += 1
                record_message_failed(self.consumer_name, topic, "json_decode_error")
                record_exception(e)
                return True

            self.log.message_received(topic, msg.partition(), msg.offset(), key)

            for attempt in range(self.kafka_config.max_retries):
                try:
                    with start_span("process_message", {"attempt": attempt + 1}):
                        if await self.process_message_async(topic, key, value):
                            duration_s = time.time() - start_time
                            duration_ms = duration_s * 1000
                            self._messages_processed += 1
                            record_message_processed(self.consumer_name, topic)
                            record_processing_duration(self.consumer_name, topic, duration_s)
                            self.log.message_processed(topic, duration_ms)
                            add_span_attributes({
                                "processing.duration_ms": duration_ms,
                                "processing.success": True
                            })
                            return True
                except Exception as e:
                    record_exception(e)
                    self.log.warning(
                        "Processing attempt failed",
                        attempt=attempt + 1,
                        max_retries=self.kafka_config.max_retries,
                        error=str(e),
                        topic=topic
                    )
                    if attempt < self.kafka_config.max_retries - 1:
                        await asyncio.sleep((2 ** attempt) * 0.1)

            duration_s = time.time() - start_time
            duration_ms = duration_s * 1000
            self.log.message_failed(topic, "max_retries_exceeded", duration_ms)
            self._messages_failed += 1
            record_message_failed(self.consumer_name, topic, "max_retries_exceeded")
            add_span_attributes({"processing.duration_ms": duration_ms, "processing.success": False})
            return True

    async def _process_and_commit(self, message, semaphore):
        try:
            if await self._handle_message_async(message):
                if not self.kafka_config.enable_auto_commit:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, self.consumer.commit, message)
        finally:
            semaphore.release()

    async def _consume_loop(self):
        """Main async consume loop with concurrent message processing"""
        semaphore = asyncio.Semaphore(self._max_concurrency)
        pending_tasks: set = set()
        loop = asyncio.get_running_loop()

        self.log.info("Async consumer loop started",max_concurrency=self._max_concurrency)

        while self.running:
            msg = await loop.run_in_executor(None, self.consumer.poll, 1.0)

            if msg is None:
                continue

            if msg.error():
                self.log.error("Consumer error", error=str(msg.error()))
                continue

            # Wait for a slot before processing
            await semaphore.acquire()

            task = asyncio.create_task(self._process_and_commit(msg, semaphore))
            pending_tasks.add(task)
            task.add_done_callback(pending_tasks.discard)

        # Wait for in-flight tasks to complete on shutdown
        if pending_tasks:
            self.log.info("Waiting for in-flight tasks to complete",
                          count=len(pending_tasks))
            await asyncio.gather(*pending_tasks, return_exceptions=True)

    def start(self):
        self.log.info("Starting async consumer", topics=self.kafka_config.topics)

        try:
            self._init_components()
            self._init_kafka_consumer()
            self.running = True
            self.log.info("Async consumer is ready and listening for messages")

            asyncio.run(self._consume_loop())

        except KafkaException as e:
            self.log.error("Kafka error", error=str(e))
            raise
        except KeyboardInterrupt:
            self.log.info("Received shutdown signal")
        finally:
            self.running = False
            self._cleanup()

    def _cleanup(self):
        self.log.info("Cleaning up consumer resources")

        self._thread_pool.shutdown(wait=False)

        if self.consumer:
            try:
                self.consumer.close()
                self.log.info("Kafka consumer closed")
            except Exception as e:
                self.log.error("Error closing consumer", error=str(e))

        self.log.info(
            "Consumer shutdown complete",
            messages_processed=self._messages_processed,
            messages_failed=self._messages_failed
        )
