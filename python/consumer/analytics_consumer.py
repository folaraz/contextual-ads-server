"""
Analytics Event Consumer

Processes events from Kafka and writes to the ads_analytics PostgreSQL schema.
Handles:
- Ad impression events (topic: ad_event, event_type: impression)
- Ad click events (topic: ad_event, event_type: click)
- Auction events (topic: auction)
- Pacing history (topic: pacing_events)

Uses Flink DataStream API for scalable processing with windowed batching.

Prerequisites:
- Kafka connector JARs must be in /opt/flink/lib/ (installed via Dockerfile.flink-python)
- Required JARs: flink-connector-kafka-*.jar, kafka-clients-*.jar
"""

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Optional, List
from datetime import datetime, timedelta
import logging
import psycopg2
from psycopg2 import sql

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from observability import init_observability

from pyflink.common import WatermarkStrategy, Time
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common.typeinfo import Types
from pyflink.common.types import Row
from pyflink.datastream import StreamExecutionEnvironment, RuntimeExecutionMode
from pyflink.datastream.connectors.kafka import KafkaSource, KafkaOffsetsInitializer
from pyflink.datastream.functions import MapFunction, ProcessWindowFunction, KeySelector, FilterFunction
from pyflink.datastream.window import TumblingProcessingTimeWindows

init_observability("analytics_consumer", version="1.0.0")
logger = logging.getLogger(__name__)



def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Analytics Event Consumer")
    parser.add_argument("--jobmanager", type=str, default="localhost",
                        help="Flink JobManager hostname (default: localhost)")
    parser.add_argument("--port", type=int, default=8081,
                        help="Flink REST API port (default: 8081)")
    return parser.parse_args()


def is_running_in_cluster() -> bool:
    """Check if we're running inside a Flink cluster (as a submitted job)."""
    return os.getenv("_FLINK_CLUSTER_MODE") == "1" or "FLINK_CONF_DIR" in os.environ


def should_submit_to_cluster() -> bool:
    """Check if we should submit job to external Flink cluster."""
    return (os.path.exists("/.dockerenv") or
            os.getenv("SUBMIT_TO_FLINK") == "true" or
            os.getenv("KAFKA_BROKERS") is not None)


class AnalyticsConfig:
    """Configuration for the analytics consumer"""

    def __init__(self):
        in_docker = is_running_in_cluster()

        # Kafka settings
        default_kafka = "kafka:29092" if in_docker else "localhost:9092"
        self.kafka_broker = os.getenv('KAFKA_BROKERS', os.getenv('KAFKA_BROKER', default_kafka))
        self.kafka_group_id = os.getenv('KAFKA_GROUP_ID', 'analytics_consumer_group')

        # Topics
        self.ad_event_topic = os.getenv('KAFKA_AD_EVENT_TOPIC', 'ad_event')
        self.auction_topic = os.getenv('KAFKA_AUCTION_TOPIC', 'auction')
        self.pacing_topic = os.getenv('KAFKA_PACING_TOPIC', 'pacing_events')

        # PostgreSQL settings
        self.pg_host = os.getenv('POSTGRES_HOST', 'postgres' if in_docker else 'localhost')
        self.pg_port = int(os.getenv('POSTGRES_PORT', '5432'))
        self.pg_database = os.getenv('POSTGRES_DB', 'contextual_ads')
        self.pg_user = os.getenv('POSTGRES_USER', 'adsuser')
        self.pg_password = os.getenv('POSTGRES_PASSWORD', 'adspassword')

        # Redis settings
        self.redis_host = os.getenv('REDIS_HOST', 'redis' if in_docker else 'localhost')
        self.redis_port = int(os.getenv('REDIS_PORT', '6379'))
        self.redis_db = int(os.getenv('REDIS_DB', '0'))

        # Sink configuration
        self.redis_enabled = os.getenv('SINK_REDIS_ENABLED', 'true').lower() == 'true'
        self.postgres_enabled = os.getenv('SINK_POSTGRES_ENABLED', 'true').lower() == 'true'

        # Processing settings
        self.batch_size = int(os.getenv('ANALYTICS_BATCH_SIZE', '100'))
        self.window_seconds = int(os.getenv('ANALYTICS_WINDOW_SECONDS', '5'))
        self.aggregation_window_seconds = int(os.getenv('AGGREGATION_WINDOW_SECONDS', '10'))
        self.parallelism = int(os.getenv('FLINK_PARALLELISM', '1'))
        self.kafka_offset_reset = os.getenv('KAFKA_AUTO_OFFSET_RESET', 'latest')


def _parse_event_time(raw_timestamp) -> datetime:
    if isinstance(raw_timestamp, str):
        try:
            return datetime.fromisoformat(raw_timestamp)
        except ValueError:
            return datetime.now()

    ts = float(raw_timestamp or 0)
    if not ts:
        return datetime.now()
    return datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts)


class _NoOpMetrics:
    def message_processed(self, *a, **kw): pass
    def message_failed(self, *a, **kw): pass
    def observe_processing_duration(self, *a, **kw): pass
    def db_operation(self, *a, **kw): pass


def _init_metrics():
    """Try to initialize MetricsManager; return no-op if the observability module is unavailable."""
    try:
        from observability.metrics import MetricsManager
        return MetricsManager(consumer_name="analytics_consumer")
    except ImportError:
        logger.warning("observability module not available, metrics disabled")
        return _NoOpMetrics()


class ParseAdEventFunction(MapFunction):
    """Parse ad event JSON (impression or click) into structured Row"""

    def open(self, runtime_context):
        self.metrics = _init_metrics()

    def map(self, value: str) -> Optional[Row]:
        start = time.perf_counter()
        try:
            event = json.loads(value)
            event_type = event.get('event_type', '').lower()
            if event_type not in ('impression', 'click'):
                return None

            event_time = _parse_event_time(event.get('timestamp', 0))

            result = Row(
                event_type=event_type,
                event_time=event_time.isoformat(),
                ad_id=int(event.get('ad_id', 0)),
                campaign_id=int(event.get('campaign_id', 0)),
                auction_id=str(event.get('auction_id', '')),
                publisher_id=str(event.get('publisher_id', '')),
                page_url=str(event.get('page_url', '')),
                click_url=str(event.get('click_url', '')),
                price_cents=int(event.get('price_cents', 0)),
                device_type=str(event.get('device_type', '')),
                user_agent=str(event.get('user_agent', '')),
                ip_address=str(event.get('ip_address', ''))
            )
            duration = time.perf_counter() - start
            self.metrics.message_processed("ad_event")
            self.metrics.observe_processing_duration("ad_event", duration)
            return result
        except Exception as e:
            self.metrics.message_failed("ad_event", type(e).__name__)
            logger.error(f"Failed to parse ad event: {e}")
            return None


class ParseAuctionEventFunction(MapFunction):
    """Parse auction event JSON into structured Row"""

    def open(self, runtime_context):
        self.metrics = _init_metrics()

    def map(self, value: str) -> Optional[Row]:
        start = time.perf_counter()
        try:
            event = json.loads(value)
            event_time = _parse_event_time(event.get('timestamp', 0))

            winner = event.get('winner')
            result = Row(
                event_time=event_time.isoformat(),
                auction_id=str(event.get('auction_id', '')),
                publisher_id=str(event.get('publisher_id', '')),
                page_url=str(event.get('page_url', '')),
                num_candidates=event.get('num_of_candidates', 0),
                num_filtered_budget=event.get('num_filtered_budget', 0),
                num_filtered_targeting=event.get('num_filtered_targeting', 0),
                num_eligible=event.get('num_eligible', 0),
                winner_ad_id=winner.get('ad_id') if winner else None,
                winner_campaign_id=winner.get('campaign_id') if winner else None,
                winning_bid_cents=int(winner.get('effective_bid', 0) * 100) if winner else None,
                winning_effective_bid=winner.get('effective_bid') if winner else None,
                winning_final_score=winner.get('final_rank_score') if winner else None,
                device_type=str(event.get('device_type', '')),
                user_agent=str(event.get('user_agent', '')),
                ip_address=str(event.get('ip_address', ''))
            )
            duration = time.perf_counter() - start
            self.metrics.message_processed("auction")
            self.metrics.observe_processing_duration("auction", duration)
            return result
        except Exception as e:
            self.metrics.message_failed("auction", type(e).__name__)
            logger.error(f"Failed to parse auction event: {e}")
            return None


class ParsePacingEventFunction(MapFunction):
    """Parse pacing event JSON into structured Row"""

    def open(self, runtime_context):
        self.metrics = _init_metrics()

    def map(self, value: str) -> Optional[Row]:
        start = time.perf_counter()
        try:
            event = json.loads(value)
            event_time = _parse_event_time(event.get('timestamp', 0))

            result = Row(
                event_time=event_time.isoformat(),
                campaign_id=int(event.get('campaign_id', 0)),
                total_budget_cents=int(event.get('total_budget', 0) * 100),
                daily_budget_cents=int(event.get('daily_budget', 0) * 100),
                remaining_budget_cents=int(event.get('remaining_budget', 0) * 100),
                spent_today_cents=int(event.get('spent_today', 0) * 100),
                effective_target_cents=int(event.get('effective_target', 0) * 100),
                remaining_days=int(event.get('remaining_days', 0)),
                campaign_time_factor=float(event.get('campaign_time_factor', 0)),
                daily_time_factor=float(event.get('daily_time_factor', 0)),
                kp=float(event.get('kp', 0)),
                ki=float(event.get('ki', 0)),
                min_multiplier=float(event.get('min_multiplier', 0)),
                max_multiplier=float(event.get('max_multiplier', 0)),
                error_normalized=float(event.get('error_normalized', 0)),
                p_term=float(event.get('p_term', 0)),
                i_term=float(event.get('i_term', 0)),
                urgency=float(event.get('urgency', 0)),
                adjustment=float(event.get('adjustment', 0)),
                cumulative_error=float(event.get('cumulative_error', 0)),
                previous_multiplier=float(event.get('previous_multiplier', 0)),
                new_multiplier=float(event.get('new_multiplier', 0)),
                status=str(event.get('status', ''))
            )
            duration = time.perf_counter() - start
            self.metrics.message_processed("pacing_events")
            self.metrics.observe_processing_duration("pacing_events", duration)
            return result
        except Exception as e:
            self.metrics.message_failed("pacing_events", type(e).__name__)
            logger.error(f"Failed to parse pacing event: {e}")
            return None


class AdIdKeySelector(KeySelector):
    def get_key(self, value):
        return value.ad_id


class CampaignIdKeySelector(KeySelector):
    def get_key(self, value):
        return value.campaign_id


class PublisherIdKeySelector(KeySelector):
    def get_key(self, value):
        return value.publisher_id


class NotNoneFilterFunction(FilterFunction):
    """Filter function to remove None values"""

    def filter(self, value):
        return value is not None

class AdMetricsAggregateFunction(ProcessWindowFunction):
    """Aggregate ad metrics within a window"""

    def process(self, key, context, elements):
        impressions = clicks = spend_cents = 0
        ad_id = int(key) if key else 0
        campaign_id = 0

        for element in elements:
            if element.event_type == 'impression':
                impressions += 1
            elif element.event_type == 'click':
                clicks += 1
            spend_cents += int(element.price_cents) if element.price_cents else 0
            if not campaign_id and hasattr(element, 'campaign_id'):
                campaign_id = element.campaign_id

        yield Row(
            ad_id=ad_id,
            campaign_id=campaign_id,
            impressions=impressions,
            clicks=clicks,
            spend_cents=spend_cents,
            window_start=int(context.window().start),
            window_end=int(context.window().end)
        )


class CampaignMetricsAggregateFunction(ProcessWindowFunction):
    """Aggregate campaign metrics within a window"""

    def process(self, key, context, elements):
        impressions = clicks = spend_cents = 0
        campaign_id = int(key) if key else 0

        for element in elements:
            if element.event_type == 'impression':
                impressions += 1
            elif element.event_type == 'click':
                clicks += 1
            spend_cents += int(element.price_cents) if element.price_cents else 0

        yield Row(
            campaign_id=campaign_id,
            impressions=impressions,
            clicks=clicks,
            spend_cents=spend_cents,
            window_start=int(context.window().start),
            window_end=int(context.window().end)
        )

class RedisMetricsSinkFunction(MapFunction):
    """Serializable Redis sink function for metrics (ad or campaign)"""

    def __init__(self, redis_host: str, redis_port: int, redis_db: int, key_prefix: str):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_db = redis_db
        self.key_prefix = key_prefix
        self.client = None

    def open(self, runtime_context):
        """Initialize Redis connection when function is opened"""
        import redis as redis_lib
        self.client = redis_lib.Redis(
            host=self.redis_host,
            port=self.redis_port,
            db=self.redis_db,
            decode_responses=True,
            socket_connect_timeout=5
        )

    def map(self, value: Row):
        import time
        from datetime import datetime, timezone

        entity_id = value.ad_id if self.key_prefix == 'ad' else value.campaign_id
        metrics_key = f"{self.key_prefix}:{entity_id}:metrics"

        pipe = self.client.pipeline(transaction=False)
        pipe.hincrby(metrics_key, "impressions", value.impressions)
        pipe.hincrby(metrics_key, "clicks", value.clicks)
        pipe.hincrby(metrics_key, "spend_cents", value.spend_cents)
        pipe.hset(metrics_key, "last_updated", int(time.time()))

        if value.impressions > 0:
            pipe.incrby(f"{self.key_prefix}:impressions:{entity_id}", value.impressions)
        if value.clicks > 0:
            pipe.incrby(f"{self.key_prefix}:clicks:{entity_id}", value.clicks)

        if self.key_prefix == 'campaign' and value.spend_cents > 0:
            today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            daily_key = f"campaign:{entity_id}:daily:{today_str}"
            pipe.hincrby(daily_key, "spend_cents", value.spend_cents)

        pipe.execute()
        return value


class AdEventWindowFunction(ProcessWindowFunction):
    """Keyed window function to batch ad events for PostgreSQL insertion"""

    def open(self, runtime_context):
        self.metrics = _init_metrics()
        self.conn = None

    def _get_conn(self):
        if self.conn is None or self.conn.closed:
            self.conn = _get_pg_connection()
        return self.conn

    def process(self, key, context, elements):
        events = list(elements)
        if events:
            start = time.perf_counter()
            try:
                _write_ad_events_to_postgres(events, self._get_conn())
                self.metrics.db_operation("write_ad_events", "success", time.perf_counter() - start)
            except Exception as e:
                self.conn = None  # reset on error so next call reconnects
                self.metrics.db_operation("write_ad_events", "error", time.perf_counter() - start)
                raise
        return []

    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()


class AuctionEventWindowFunction(ProcessWindowFunction):
    """Keyed window function to batch auction events for PostgreSQL insertion"""

    def open(self, runtime_context):
        self.metrics = _init_metrics()
        self.conn = None

    def _get_conn(self):
        if self.conn is None or self.conn.closed:
            self.conn = _get_pg_connection()
        return self.conn

    def process(self, key, context, elements):
        events = list(elements)
        if events:
            start = time.perf_counter()
            try:
                _write_auction_events_to_postgres(events, self._get_conn())
                self.metrics.db_operation("write_auction_events", "success", time.perf_counter() - start)
            except Exception as e:
                self.conn = None
                self.metrics.db_operation("write_auction_events", "error", time.perf_counter() - start)
                raise
        return []

    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()


class PacingEventWindowFunction(ProcessWindowFunction):
    """Keyed window function to batch pacing events for PostgreSQL insertion"""

    def open(self, runtime_context):
        self.metrics = _init_metrics()
        self.conn = None

    def _get_conn(self):
        if self.conn is None or self.conn.closed:
            self.conn = _get_pg_connection()
        return self.conn

    def process(self, key, context, elements):
        events = list(elements)
        if events:
            start = time.perf_counter()
            try:
                _write_pacing_events_to_postgres(events, self._get_conn())
                self.metrics.db_operation("write_pacing_events", "success", time.perf_counter() - start)
            except Exception as e:
                self.conn = None
                self.metrics.db_operation("write_pacing_events", "error", time.perf_counter() - start)
                raise
        return []

    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()

def _get_pg_connection():
    """Get PostgreSQL connection from environment"""
    import psycopg2
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        database=os.getenv('POSTGRES_DB', 'contextual_ads'),
        user=os.getenv('POSTGRES_USER', 'adsuser'),
        password=os.getenv('POSTGRES_PASSWORD', 'adspassword')
    )


def _ensure_partitions_exist(table_name: str, event_times: List[datetime], schema_name: str = "ads_analytics"):
    """
    Ensure daily partitions exist for all event_times in the batch.
    Creates missing partitions on-the-fly to avoid CheckViolation errors.
    """
    # Use set comprehension for a cleaner, faster extraction
    dates_needed = {et.date() for et in event_times}

    if not dates_needed:
        return

    conn = _get_pg_connection()
    conn.autocommit = True

    try:
        for partition_date in dates_needed:
            next_date = partition_date + timedelta(days=1)
            partition_name = f"{table_name}_{partition_date.strftime('%Y_%m_%d')}"

            try:
                # Use context manager to ensure the cursor is always closed,
                # even if an exception is raised.
                with conn.cursor() as cursor:

                    # 1. Check if partition exists
                    cursor.execute(
                        """
                        SELECT 1 
                        FROM pg_catalog.pg_class c 
                        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace 
                        WHERE n.nspname = %s AND c.relname = %s
                        """,
                        (schema_name, partition_name)
                    )

                    if cursor.fetchone() is not None:
                        continue  # Partition exists, move to the next date

                    # 2. Create partition
                    cursor.execute(
                        sql.SQL(
                            "CREATE TABLE {schema}.{partition} "
                            "PARTITION OF {schema}.{parent} "
                            "FOR VALUES FROM (%s) TO (%s)"
                        ).format(
                            schema=sql.Identifier(schema_name),
                            partition=sql.Identifier(partition_name),
                            parent=sql.Identifier(table_name),
                        ),
                        (str(partition_date), str(next_date))
                    )
                    logger.info(f"Created partition {partition_name}")

            except psycopg2.errors.DuplicateTable:
                logger.debug(f"Partition {partition_name} already exists (caught DuplicateTable).")
            except Exception as e:
                logger.error(f"Partition {partition_name} creation failed: {e}", exc_info=True)
                raise
    finally:
        conn.close()

def _write_ad_events_to_postgres(events: List[Row], conn=None):
    """Write ad events to PostgreSQL"""
    if not events:
        return

    from psycopg2.extras import execute_values

    owns_conn = conn is None
    if owns_conn:
        conn = _get_pg_connection()
    try:
        cursor = conn.cursor()
        impressions, clicks = [], []
        all_event_times = []

        for event in events:
            if event is None:
                continue
            event_time = datetime.fromisoformat(event.event_time)
            all_event_times.append(event_time)
            ip_addr = event.ip_address or None

            data = (event_time, event.ad_id, event.campaign_id, event.auction_id,
                    event.publisher_id, event.page_url, event.price_cents,
                    event.device_type, event.user_agent, ip_addr)

            if event.event_type == 'impression':
                impressions.append(data)
            elif event.event_type == 'click':
                clicks.append(data + (event.click_url,))

        if impressions:
            _ensure_partitions_exist('ad_impression_events', all_event_times)
        if clicks:
            _ensure_partitions_exist('ad_click_events', all_event_times)

        if impressions:
            execute_values(cursor, """
                INSERT INTO ads_analytics.ad_impression_events
                (event_time, ad_id, campaign_id, auction_id, publisher_id, page_url,
                 price_cents, device_type, user_agent, ip_address)
                VALUES %s
            """, impressions)
            logger.info(f"Inserted {len(impressions)} impression events")

        if clicks:
            execute_values(cursor, """
                INSERT INTO ads_analytics.ad_click_events
                (event_time, ad_id, campaign_id, auction_id, publisher_id, page_url,
                 price_cents, device_type, user_agent, ip_address, click_url)
                VALUES %s
            """, clicks)
            logger.info(f"Inserted {len(clicks)} click events")

        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def _write_auction_events_to_postgres(events: List[Row], conn=None):
    """Write auction events to PostgreSQL"""
    if not events:
        return

    from psycopg2.extras import execute_values

    owns_conn = conn is None
    if owns_conn:
        conn = _get_pg_connection()
    try:
        cursor = conn.cursor()
        records = []
        all_event_times = []

        for event in events:
            if event is None:
                continue
            event_time = datetime.fromisoformat(event.event_time)
            all_event_times.append(event_time)
            records.append((
                event_time, event.auction_id,
                event.publisher_id, event.page_url, event.num_candidates,
                event.num_filtered_budget, event.num_filtered_targeting, event.num_eligible,
                event.winner_ad_id, event.winner_campaign_id, event.winning_bid_cents,
                event.winning_effective_bid, event.winning_final_score,
                event.device_type, event.user_agent, event.ip_address or None
            ))

        if records:
            _ensure_partitions_exist('auction_events', all_event_times)

            execute_values(cursor, """
                INSERT INTO ads_analytics.auction_events
                (event_time, auction_id, publisher_id, page_url, num_candidates,
                 num_filtered_budget, num_filtered_targeting, num_eligible,
                 winner_ad_id, winner_campaign_id, winning_bid_cents,
                 winning_effective_bid, winning_final_score, device_type, user_agent, ip_address)
                VALUES %s
            """, records)
            logger.info(f"Inserted {len(records)} auction events")

        conn.commit()
    finally:
        if owns_conn:
            conn.close()


def _write_pacing_events_to_postgres(events: List[Row], conn=None):
    """Write pacing events to PostgreSQL"""
    if not events:
        return

    from psycopg2.extras import execute_values

    owns_conn = conn is None
    if owns_conn:
        conn = _get_pg_connection()
    try:
        cursor = conn.cursor()
        records = []
        all_event_times = []

        for event in events:
            if event is None:
                continue
            event_time = datetime.fromisoformat(event.event_time)
            all_event_times.append(event_time)
            records.append((
                event_time, event.campaign_id,
                event.total_budget_cents, event.daily_budget_cents,
                event.remaining_budget_cents, event.spent_today_cents,
                event.effective_target_cents, event.remaining_days,
                event.campaign_time_factor, event.daily_time_factor,
                event.kp, event.ki, event.min_multiplier, event.max_multiplier,
                event.error_normalized, event.p_term, event.i_term,
                event.urgency, event.adjustment, event.cumulative_error,
                event.previous_multiplier, event.new_multiplier, event.status
            ))

        if records:
            _ensure_partitions_exist('pacing_history', all_event_times)

            execute_values(cursor, """
                INSERT INTO ads_analytics.pacing_history
                (event_time, campaign_id, total_budget_cents, daily_budget_cents,
                 remaining_budget_cents, spent_today_cents, effective_target_cents,
                 remaining_days, campaign_time_factor, daily_time_factor,
                 kp, ki, min_multiplier, max_multiplier,
                 error_normalized, p_term, i_term, urgency, adjustment, cumulative_error,
                 previous_multiplier, new_multiplier, status)
                VALUES %s
            """, records)
            logger.info(f"Inserted {len(records)} pacing events")

        conn.commit()
    finally:
        if owns_conn:
            conn.close()


class AnalyticsEventConsumer:
    """
    Flink-based analytics event consumer.

    Reads from multiple Kafka topics and writes to:
    - PostgreSQL ads_analytics schema (historical data)
    - Redis (real-time metrics for ad serving)
    """

    def __init__(self, config: AnalyticsConfig):
        self.config = config
        self.env = None

    def _init_environment(self):
        """Initialize the Flink execution environment with persistent checkpoint storage"""
        from pyflink.common import Configuration

        checkpoint_interval = int(os.getenv('FLINK_CHECKPOINT_INTERVAL_MS', '60000'))
        checkpoint_dir = os.getenv('FLINK_CHECKPOINT_DIR', 'file:///opt/flink/data/checkpoints')
        savepoint_dir = os.getenv('FLINK_SAVEPOINT_DIR', 'file:///opt/flink/data/savepoints')

        # Set checkpoint/savepoint dirs via Configuration so they're baked into the job graph.
        # This supplements the cluster-level FLINK_PROPERTIES in docker-compose.
        config = Configuration()
        config.set_string("state.checkpoints.dir", checkpoint_dir)
        config.set_string("state.savepoints.dir", savepoint_dir)

        self.env = StreamExecutionEnvironment.get_execution_environment(config)
        self.env.set_runtime_mode(RuntimeExecutionMode.STREAMING)
        self.env.set_parallelism(self.config.parallelism)
        self.env.enable_checkpointing(checkpoint_interval)

        logger.info(f"Flink environment initialized (parallelism={self.config.parallelism}, "
                     f"checkpoint_interval={checkpoint_interval}ms, checkpoint_dir={checkpoint_dir})")

    def _create_kafka_source(self, topics: List[str], group_id: str) -> KafkaSource:
        """Create Kafka source for given topics.
        """
        if self.config.kafka_offset_reset == 'earliest':
            offsets = KafkaOffsetsInitializer.earliest()
        else:
            offsets = KafkaOffsetsInitializer.latest()

        return (
            KafkaSource.builder()
            .set_bootstrap_servers(self.config.kafka_broker)
            .set_topics(*topics)
            .set_group_id(group_id)
            .set_starting_offsets(offsets)
            .set_value_only_deserializer(SimpleStringSchema())
            .build()
        )

    def _setup_ad_events_pipeline(self):
        """Setup pipeline for ad events with PostgreSQL and Redis sinks"""
        ad_event_type = Types.ROW_NAMED(
            ['event_type', 'event_time', 'ad_id', 'campaign_id', 'auction_id',
             'publisher_id', 'page_url', 'click_url', 'price_cents',
             'device_type', 'user_agent', 'ip_address'],
            [Types.STRING(), Types.STRING(), Types.INT(), Types.INT(), Types.STRING(),
             Types.STRING(), Types.STRING(), Types.STRING(), Types.INT(),
             Types.STRING(), Types.STRING(), Types.STRING()]
        )

        source = self._create_kafka_source(
            [self.config.ad_event_topic],
            f"{self.config.kafka_group_id}_ad_events"
        )

        stream = self.env.from_source(source, WatermarkStrategy.no_watermarks(), "Ad Events Source")
        parsed = stream.map(ParseAdEventFunction(), output_type=ad_event_type)
        valid = parsed.filter(NotNoneFilterFunction())

        # PostgreSQL sink (keyed window for parallelism)
        if self.config.postgres_enabled:
            valid.key_by(AdIdKeySelector()) \
                .window(TumblingProcessingTimeWindows.of(Time.seconds(self.config.window_seconds))) \
                .process(AdEventWindowFunction(), output_type=Types.STRING())

        # Redis metrics (aggregated)
        if self.config.redis_enabled:
            self._setup_redis_metrics_pipeline(valid)

        logger.info(f"Ad events pipeline configured (topic: {self.config.ad_event_topic})")

    def _setup_redis_metrics_pipeline(self, valid_stream):
        """Setup Redis metrics aggregation pipeline"""
        ad_metrics_type = Types.ROW_NAMED(
            ['ad_id', 'campaign_id', 'impressions', 'clicks', 'spend_cents', 'window_start', 'window_end'],
            [Types.INT(), Types.INT(), Types.INT(), Types.INT(), Types.INT(), Types.LONG(), Types.LONG()]
        )
        campaign_metrics_type = Types.ROW_NAMED(
            ['campaign_id', 'impressions', 'clicks', 'spend_cents', 'window_start', 'window_end'],
            [Types.INT(), Types.INT(), Types.INT(), Types.INT(), Types.LONG(), Types.LONG()]
        )

        window_size = Time.seconds(self.config.aggregation_window_seconds)

        # Ad-level metrics
        ad_metrics = valid_stream \
            .key_by(AdIdKeySelector()) \
            .window(TumblingProcessingTimeWindows.of(window_size)) \
            .process(AdMetricsAggregateFunction(), output_type=ad_metrics_type)

        ad_redis_sink = RedisMetricsSinkFunction(
            self.config.redis_host, self.config.redis_port, self.config.redis_db, 'ad'
        )
        ad_metrics.map(ad_redis_sink, output_type=ad_metrics_type).print()

        # Campaign-level metrics
        campaign_metrics = valid_stream \
            .key_by(CampaignIdKeySelector()) \
            .window(TumblingProcessingTimeWindows.of(window_size)) \
            .process(CampaignMetricsAggregateFunction(), output_type=campaign_metrics_type)

        campaign_redis_sink = RedisMetricsSinkFunction(
            self.config.redis_host, self.config.redis_port, self.config.redis_db, 'campaign'
        )
        campaign_metrics.map(campaign_redis_sink, output_type=campaign_metrics_type).print()

    def _setup_auction_events_pipeline(self):
        """Setup pipeline for auction events"""
        auction_event_type = Types.ROW_NAMED(
            ['event_time', 'auction_id', 'publisher_id', 'page_url',
             'num_candidates', 'num_filtered_budget', 'num_filtered_targeting', 'num_eligible',
             'winner_ad_id', 'winner_campaign_id', 'winning_bid_cents',
             'winning_effective_bid', 'winning_final_score',
             'device_type', 'user_agent', 'ip_address'],
            [Types.STRING(), Types.STRING(), Types.STRING(), Types.STRING(),
             Types.INT(), Types.INT(), Types.INT(), Types.INT(),
             Types.INT(), Types.INT(), Types.INT(),
             Types.FLOAT(), Types.FLOAT(),
             Types.STRING(), Types.STRING(), Types.STRING()]
        )

        source = self._create_kafka_source(
            [self.config.auction_topic],
            f"{self.config.kafka_group_id}_auctions"
        )

        stream = self.env.from_source(source, WatermarkStrategy.no_watermarks(), "Auction Events Source")
        parsed = stream.map(ParseAuctionEventFunction(), output_type=auction_event_type)
        valid = parsed.filter(NotNoneFilterFunction())

        valid.key_by(PublisherIdKeySelector()) \
            .window(TumblingProcessingTimeWindows.of(Time.seconds(self.config.window_seconds))) \
            .process(AuctionEventWindowFunction(), output_type=Types.STRING())

        logger.info(f"Auction events pipeline configured (topic: {self.config.auction_topic})")

    def _setup_pacing_events_pipeline(self):
        """Setup pipeline for pacing history events"""
        pacing_event_type = Types.ROW_NAMED(
            ['event_time', 'campaign_id',
             'total_budget_cents', 'daily_budget_cents', 'remaining_budget_cents',
             'spent_today_cents', 'effective_target_cents', 'remaining_days',
             'campaign_time_factor', 'daily_time_factor',
             'kp', 'ki', 'min_multiplier', 'max_multiplier',
             'error_normalized', 'p_term', 'i_term', 'urgency',
             'adjustment', 'cumulative_error',
             'previous_multiplier', 'new_multiplier', 'status'],
            [Types.STRING(), Types.INT(),
             Types.LONG(), Types.LONG(), Types.LONG(),
             Types.LONG(), Types.LONG(), Types.INT(),
             Types.FLOAT(), Types.FLOAT(),
             Types.FLOAT(), Types.FLOAT(), Types.FLOAT(), Types.FLOAT(),
             Types.FLOAT(), Types.FLOAT(), Types.FLOAT(), Types.FLOAT(),
             Types.FLOAT(), Types.FLOAT(),
             Types.FLOAT(), Types.FLOAT(), Types.STRING()]
        )

        source = self._create_kafka_source(
            [self.config.pacing_topic],
            f"{self.config.kafka_group_id}_pacing"
        )

        stream = self.env.from_source(source, WatermarkStrategy.no_watermarks(), "Pacing Events Source")
        parsed = stream.map(ParsePacingEventFunction(), output_type=pacing_event_type)
        valid = parsed.filter(NotNoneFilterFunction())

        valid.key_by(CampaignIdKeySelector()) \
            .window(TumblingProcessingTimeWindows.of(Time.seconds(self.config.window_seconds))) \
            .process(PacingEventWindowFunction(), output_type=Types.STRING())

        logger.info(f"Pacing events pipeline configured (topic: {self.config.pacing_topic})")

    def start(self):
        """Start the analytics consumer"""
        logger.info("=" * 60)
        logger.info("  Analytics Event Consumer")
        logger.info("=" * 60)
        logger.info(f"  Kafka: {self.config.kafka_broker}")
        logger.info(f"  Topics: {self.config.ad_event_topic}, {self.config.auction_topic}, {self.config.pacing_topic}")
        logger.info(f"  PostgreSQL: {self.config.pg_host}:{self.config.pg_port}/{self.config.pg_database}")
        logger.info(f"  Redis: {self.config.redis_host}:{self.config.redis_port}")
        logger.info(f"  Sinks: PostgreSQL={self.config.postgres_enabled}, Redis={self.config.redis_enabled}")
        logger.info("=" * 60)

        try:
            logger.info("Initializing Flink environment...")
            self._init_environment()
            logger.info("Setting up ad events pipeline...")
            self._setup_ad_events_pipeline()
            logger.info("Setting up auction events pipeline...")
            self._setup_auction_events_pipeline()
            logger.info("Setting up pacing events pipeline...")
            self._setup_pacing_events_pipeline()
            logger.info("Starting Flink job execution...")
            self.env.execute("Analytics Event Consumer")
        except Exception as e:
            logger.error(f"Failed during pipeline setup: {e}", exc_info=True)
            raise


def submit_job_via_rest_api(jobmanager_host: str, jobmanager_port: int):
    """Submit the PyFlink job to Flink cluster using REST API."""
    logger.info(f"Submitting job to Flink REST API at {jobmanager_host}:{jobmanager_port}")

    script_path = os.path.abspath(__file__)
    cmd = [
        "flink", "run",
        "--jobmanager", f"{jobmanager_host}:{jobmanager_port}",
        "--python", script_path,
        "--pyExecutable", "python3"
    ]

    logger.info(f"Executing: {' '.join(cmd)}")

    try:
        env = os.environ.copy()
        env['_FLINK_CLUSTER_MODE'] = '1'

        result = subprocess.run(
            cmd,
            check=True,
            env=env,
            capture_output=True,
            text=True
        )
        logger.info(f"Job submitted successfully: {result.stdout}")
        return True
    except FileNotFoundError:
        logger.error("Flink CLI not found in PATH")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"Job submission failed: {e.stderr}")
        return False


def main():
    args = parse_args()
    config = AnalyticsConfig()

    if is_running_in_cluster():
        logger.info("Running inside Flink cluster - executing job")
        consumer = AnalyticsEventConsumer(config)
        try:
            consumer.start()
        except KeyboardInterrupt:
            logger.info("Job stopped by user")
        except Exception as e:
            logger.error(f"Analytics consumer failed: {e}", exc_info=True)
            sys.exit(1)
    elif should_submit_to_cluster():
        jobmanager_host = os.getenv('FLINK_JOBMANAGER_HOST', 'flink-jobmanager')
        jobmanager_port = int(os.getenv('FLINK_JOBMANAGER_PORT', '8081'))

        logger.info(f"Submitting job to Flink cluster at {jobmanager_host}:{jobmanager_port}")
        success = submit_job_via_rest_api(jobmanager_host, jobmanager_port)

        if not success:
            logger.error("Failed to submit job to Flink cluster")
            sys.exit(1)

        logger.info("Job submitted successfully. Monitor at http://{}:{}".format(
            jobmanager_host, jobmanager_port))
    # Run locally
    else:
        logger.info("Running in local mode")
        consumer = AnalyticsEventConsumer(config)
        try:
            consumer.start()
        except KeyboardInterrupt:
            logger.info("Job stopped by user")
        except Exception as e:
            logger.error(f"Analytics consumer failed: {e}", exc_info=True)
            sys.exit(1)


if __name__ == '__main__':
    main()
