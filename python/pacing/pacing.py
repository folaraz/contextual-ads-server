import os
import sys
import time as time_module
from dataclasses import dataclass, field
from datetime import datetime, date, timezone
from typing import Optional, List, Dict

import redis

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import RedisConfig, PacingConfig, KafkaConfig
from pacing.redis_cache import RedisCache, CampaignKeys


# Constants
ACTIVE_CAMPAIGNS_KEY = "active_campaigns"
DAILY_METRICS_TTL = 172800


@dataclass
class CampaignState:
    campaign_id: str = ""
    advertiser_id: str = ""
    total_budget: float = 0.0
    daily_budget: float = 0.0
    start_time: int = 0
    end_time: int = 0
    status: str = ""
    current_multiplier: float = 1.0
    previous_multiplier: float = 1.0
    integral_sum: float = 0.0

    @property
    def is_active(self) -> bool:
        return self.status == "active"


    sim_time: Optional[float] = None

    def _now(self) -> datetime:
        if self.sim_time is not None:
            return datetime.fromtimestamp(self.sim_time, tz=timezone.utc)
        return datetime.now(timezone.utc)

    def _now_ts(self) -> float:
        if self.sim_time is not None:
            return self.sim_time
        return datetime.now(timezone.utc).timestamp()

    @property
    def remaining_seconds(self) -> float:
        return max(0.0, self.end_time - self._now_ts())

    @property
    def remaining_days(self) -> int:
        return max(0, int(self.remaining_seconds / 86400))

    @property
    def campaign_time_factor(self) -> float:
        now = self._now_ts()
        duration = self.end_time - self.start_time
        if duration <= 0:
            return 1.0
        elapsed = now - self.start_time
        return min(1.0, max(0.0, elapsed / duration))

    @property
    def daily_time_factor(self) -> float:
        now = self._now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        seconds_into_day = (now - today_start).total_seconds()
        return min(1.0, max(0.0, seconds_into_day / 86400))


@dataclass
class CampaignMetrics:
    """Cumulative metrics for a campaign."""
    impressions: int = 0
    clicks: int = 0
    spend_cents: int = 0
    last_updated: int = 0

    @property
    def spend_dollars(self) -> float:
        return self.spend_cents / 100.0

@dataclass
class DailyMetrics:
    """Daily spend tracking for a campaign."""
    spend_cents: int = 0

    @property
    def spent_dollars(self) -> float:
        return self.spend_cents / 100.0



@dataclass
class PIConfig:
    """PI controller configuration."""
    kp: float = 0.15
    ki: float = 0.04
    min_multiplier: float = 0.10
    max_multiplier: float = 2.0
    max_integral: float = 5.0
    accel_limit_up: float = 0.08
    accel_limit_down: float = 0.04


@dataclass
class PacingResult:
    """Result of a pacing calculation."""
    multiplier: float = 1.0
    error_normalized: float = 0.0
    p_term: float = 0.0
    i_term: float = 0.0
    status: str = "ok"
    debug: Dict = field(default_factory=dict)



class PacingService:

    def __init__(self, redis_client: redis.Redis):
        self.cache = RedisCache(redis_client)


    def get_active_campaign_ids(self) -> List[str]:
        return self.cache.smembers(ACTIVE_CAMPAIGNS_KEY)

    def get_state(self, campaign_id: str) -> Optional[CampaignState]:
        data = self.cache.hgetall(CampaignKeys.state(campaign_id))
        if not data:
            return None

        return CampaignState(
            campaign_id=self.cache.get_hash_str(data, "campaign_id"),
            advertiser_id=self.cache.get_hash_str(data, "advertiser_id"),
            total_budget=self.cache.get_hash_float(data, "total_budget"),
            daily_budget=self.cache.get_hash_float(data, "daily_budget"),
            start_time=self.cache.get_hash_int(data, "start_time"),
            end_time=self.cache.get_hash_int(data, "end_time"),
            status=self.cache.get_hash_str(data, "status"),
            current_multiplier=self.cache.get_hash_float(data, "current_multiplier", 1.0),
            previous_multiplier=self.cache.get_hash_float(data, "previous_multiplier", 1.0),
            integral_sum=self.cache.get_hash_float(data, "integral_sum"),
        )

    def get_metrics(self, campaign_id: str) -> Optional[CampaignMetrics]:
        data = self.cache.hgetall(CampaignKeys.metrics(campaign_id))
        if not data:
            return None

        return CampaignMetrics(
            impressions=self.cache.get_hash_int(data, "impressions"),
            clicks=self.cache.get_hash_int(data, "clicks"),
            spend_cents=self.cache.get_hash_int(data, "spend_cents"),
            last_updated=self.cache.get_hash_int(data, "last_updated"),
        )

    def get_daily_metrics(self, campaign_id: str, dt: Optional[date] = None) -> Optional[DailyMetrics]:
        data = self.cache.hgetall(CampaignKeys.daily(campaign_id, dt))
        if not data:
            return None

        return DailyMetrics(
            spend_cents=self.cache.get_hash_int(data, "spend_cents"),
        )

    def get_pi_config(self, campaign_id: str) -> PIConfig:
        data = self.cache.hgetall(CampaignKeys.pi_config(campaign_id))
        if not data:
            return PIConfig()

        return PIConfig(
            kp=self.cache.get_hash_float(data, "kp", 0.15),
            ki=self.cache.get_hash_float(data, "ki", 0.04),
            min_multiplier=self.cache.get_hash_float(data, "min_multiplier", 0.10),
            max_multiplier=self.cache.get_hash_float(data, "max_multiplier", 2.0),
            max_integral=self.cache.get_hash_float(data, "max_integral", 5.0),
            accel_limit_up=self.cache.get_hash_float(data, "accel_limit_up", 0.08),
            accel_limit_down=self.cache.get_hash_float(data, "accel_limit_down", 0.04),
        )

    def ensure_daily_metrics(self, campaign_id: str) -> bool:
        key = CampaignKeys.daily_today(campaign_id)

        if self.cache.exists(key):
            return False

        self.cache.hset(key, mapping={
            "spend_cents": 0,
        }, ttl=DAILY_METRICS_TTL)
        return True

    def _save_pacing_state(
            self,
            campaign_id: str,
            multiplier: float,
            prev_multiplier: float,
            integral_sum: float,
    ) -> None:
        now = datetime.now(timezone.utc).timestamp()

        self.cache.hset(
            CampaignKeys.state(campaign_id),
            mapping={
                "current_multiplier": str(multiplier),
                "previous_multiplier": str(prev_multiplier),
                "integral_sum": str(integral_sum),
                "last_pid_run": str(now),
            }
        )


    def _calculate_urgency(self, state: CampaignState) -> float:
        return 0.3 * (1.0 + state.campaign_time_factor ** 2) + 0.7 * (1.0 + state.daily_time_factor ** 2)

    def calculate_pacing(self, campaign_id: str, sim_time: Optional[float] = None) -> PacingResult:

        # Ensure daily metrics exist
        self.ensure_daily_metrics(campaign_id)

        # Load all data
        state = self.get_state(campaign_id)
        if not state:
            return PacingResult(status="no_state")

        # Inject simulated time if provided
        if sim_time is not None:
            state.sim_time = sim_time

        metrics = self.get_metrics(campaign_id)
        if not metrics:
            return PacingResult(status="no_metrics")

        daily = self.get_daily_metrics(campaign_id)
        config = self.get_pi_config(campaign_id)

        # Calculate error
        error_result = self._calculate_error(state, metrics, daily)

        prev = state.current_multiplier

        if error_result.status == "budget_exhausted":
            self._save_pacing_state(campaign_id, 0.0, prev, state.integral_sum)
            error_result.multiplier = 0.0
            error_result.debug.update({
                "previous_multiplier": prev,
                "kp": config.kp, "ki": config.ki,
                "min_multiplier": config.min_multiplier,
                "max_multiplier": config.max_multiplier,
                "cumulative_error": state.integral_sum,
            })
            return error_result

        if error_result.status == "target_too_low":
            self._save_pacing_state(campaign_id, prev, prev, state.integral_sum)
            error_result.multiplier = prev
            error_result.debug.update({
                "previous_multiplier": prev,
                "kp": config.kp, "ki": config.ki,
                "min_multiplier": config.min_multiplier,
                "max_multiplier": config.max_multiplier,
                "cumulative_error": state.integral_sum,
            })
            return error_result

        if error_result.status != "ok":
            return error_result

        error_norm = error_result.error_normalized

        # Calculate urgency (increases as deadline approaches)
        urgency = self._calculate_urgency(state)

        # Proportional term
        p_term = config.kp * error_norm * urgency


        prev_cumulative = state.integral_sum
        at_upper_limit = prev >= config.max_multiplier and error_norm > 0  # underspend but already at ceiling
        at_lower_limit = prev <= config.min_multiplier and error_norm < 0  # overspend but already at floor
        if at_upper_limit or at_lower_limit:
            cumulative_error = prev_cumulative
        else:
            cumulative_error = prev_cumulative + error_norm
            cumulative_error = max(-config.max_integral, min(config.max_integral, cumulative_error))
        i_term = config.ki * cumulative_error * urgency

        adjustment = max(-0.5, min(1.0, p_term + i_term))
        desired = prev + adjustment

        # Apply asymmetric acceleration limits.
        multiplier_range = config.max_multiplier - config.min_multiplier
        if desired > prev:
            max_change = config.accel_limit_up * multiplier_range
        else:
            max_change = config.accel_limit_down * multiplier_range

        if desired > prev + max_change:
            new_multiplier = prev + max_change
        elif desired < prev - max_change:
            new_multiplier = prev - max_change
        else:
            new_multiplier = desired

        # Apply bounds
        new_multiplier = max(config.min_multiplier, min(config.max_multiplier, new_multiplier))

        self._save_pacing_state(campaign_id, new_multiplier, prev, cumulative_error)

        return PacingResult(
            multiplier=new_multiplier,
            error_normalized=error_norm,
            p_term=p_term,
            i_term=i_term,
            status="ok",
            debug={
                **error_result.debug,
                "kp": config.kp,
                "ki": config.ki,
                "min_multiplier": config.min_multiplier,
                "max_multiplier": config.max_multiplier,
                "accel_limit_up": config.accel_limit_up,
                "accel_limit_down": config.accel_limit_down,
                "previous_multiplier": prev,
                "urgency": urgency,
                "adjustment": adjustment,
                "cumulative_error": cumulative_error,
                "integral_frozen": at_upper_limit or at_lower_limit,
            },
        )


    def _calculate_error(
            self,
            state: CampaignState,
            metrics: CampaignMetrics,
            daily: Optional[DailyMetrics],
    ) -> PacingResult:
        spent_today = daily.spent_dollars if daily else 0.0

        budget_debug = {
            "remaining_budget": state.total_budget - metrics.spend_dollars,
            "total_budget": state.total_budget,
            "daily_budget": state.daily_budget,
            "spent_today": spent_today,
            "remaining_days": state.remaining_days,
            "campaign_time_factor": state.campaign_time_factor,
            "daily_time_factor": state.daily_time_factor,
        }

        # Remaining total budget
        remaining_budget = state.total_budget - metrics.spend_dollars
        if remaining_budget <= 0:
            return PacingResult(
                status="budget_exhausted", error_normalized=-1.0,
                debug=budget_debug,
            )

        # Daily budget exhaustion check
        if daily and state.daily_budget > 0:
            if daily.spent_dollars >= state.daily_budget:
                return PacingResult(
                    status="budget_exhausted", error_normalized=-1.0,
                    debug=budget_debug,
                )

        # Calculate ideal daily spend
        remaining_hours = state.remaining_seconds / 3600
        remaining_hours = max(1.0, remaining_hours)
        ideal_daily = (remaining_budget / remaining_hours) * 24

        # Apply daily limit
        effective_target = min(ideal_daily, state.daily_budget) if state.daily_budget > 0 else ideal_daily

        time_factor = max(0.05, state.daily_time_factor)

        effective_target *= time_factor

        if effective_target < 0.01:
            return PacingResult(status="target_too_low", error_normalized=0.0,
                                debug=budget_debug)

        # Normalized error: positive = underspending, negative = overspending
        error_abs = effective_target - spent_today
        error_norm = error_abs / effective_target

        error_norm = max(-1.5, min(1.5, error_norm))

        return PacingResult(
            status="ok",
            error_normalized=error_norm,
            debug={
                **budget_debug,
                "ideal_daily": ideal_daily,
                "effective_target": effective_target,
                "error_absolute": error_abs,
            },
        )


class PacingWorker:

    def __init__(
        self,
        redis_client: redis.Redis,
        kafka_config: KafkaConfig,
        interval: int = 30,
    ):
        from kafka import KafkaProducer
        from observability import get_structured_logger, get_metrics_manager
        import json

        self.service = PacingService(redis_client)
        self.interval = interval
        self._running = False
        self.log = get_structured_logger("pacing_worker")
        self.metrics = get_metrics_manager("pacing_worker")

        # Initialize Kafka producer
        self.producer = KafkaProducer(
            bootstrap_servers=kafka_config.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
        )
        self.topic = kafka_config.topics[0] if kafka_config.topics else "pacing_events"
        self.log.info("Kafka producer initialized", topic=self.topic)

    def _publish_result(self, campaign_id: str, result: PacingResult) -> None:
        message = {
            "campaign_id": campaign_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "new_multiplier": result.multiplier,
            "error_normalized": result.error_normalized,
            "p_term": result.p_term,
            "i_term": result.i_term,
            "status": result.status,
            **result.debug,
        }
        self.producer.send(self.topic, key=campaign_id, value=message)

    def run_once(self) -> Dict[str, PacingResult]:
        from observability import start_span, add_span_attributes, record_exception

        results = {}

        with start_span("pacing_run_once"):
            campaign_ids = self.service.get_active_campaign_ids()
            add_span_attributes({"campaigns.count": len(campaign_ids)})

            for cid in campaign_ids:
                try:
                    with start_span("calculate_pacing", {"campaign_id": cid}):
                        result = self.service.calculate_pacing(cid)
                        results[cid] = result

                        # Record metrics
                        self.metrics.record_pacing_calculation(
                            campaign_id=cid,
                            multiplier=result.multiplier,
                            status=result.status,
                        )

                        # Publish to Kafka (fire and forget, non-blocking)
                        if result.status in ("ok", "budget_exhausted"):
                            self._publish_result(cid, result)

                except Exception as e:
                    record_exception(e)
                    self.log.error("Pacing error", campaign_id=cid, error=str(e))
                    results[cid] = PacingResult(status=f"error: {e}")

            # Ensure all messages are sent
            self.producer.flush()

        return results

    def run(self) -> None:
        from observability import start_span

        self.log.info("Pacing worker started", interval=self.interval)
        self._running = True

        while self._running:
            start = time_module.time()

            try:
                with start_span("pacing_cycle"):
                    results = self.run_once()

                    if not results:
                        self.log.info("No active campaigns")
                    else:
                        self.log.info("Processed campaigns", count=len(results))
                        for cid, result in results.items():
                            if result.status == "ok":
                                self.log.info(
                                    "Campaign pacing calculated",
                                    campaign_id=cid,
                                    multiplier=round(result.multiplier, 4),
                                    error=round(result.error_normalized, 3),
                                    p_term=round(result.p_term, 4),
                                    i_term=round(result.i_term, 4),
                                )
                            else:
                                self.log.warning("Campaign pacing issue", campaign_id=cid, status=result.status)

            except Exception as e:
                self.log.error("Worker error", error=str(e))

            # Sleep for remainder of interval
            elapsed = time_module.time() - start
            sleep_time = max(0.0, self.interval - elapsed)
            time_module.sleep(sleep_time)

    def stop(self) -> None:
        """Stop the worker."""
        self._running = False
        self.producer.close()
        self.log.info("Pacing worker stopped")


if __name__ == '__main__':
    from config import Topics
    from observability import init_observability, get_structured_logger

    init_observability("pacing_worker", version="1.0.0")
    log = get_structured_logger("pacing_worker")

    log.info("Starting Pacing Worker...")

    redis_config = RedisConfig.from_env()
    pacing_config = PacingConfig.from_env()
    kafka_config = KafkaConfig.from_env(
        default_topics=[Topics.PACING_EVENTS],
        default_group="pacing_worker",
    )

    log.info("Configuration loaded",
             redis_host=redis_config.host,
             interval=pacing_config.interval_seconds)

    redis_client = redis.Redis(
        host=redis_config.host,
        port=redis_config.port,
        db=redis_config.db,
    )

    worker = PacingWorker(
        redis_client,
        kafka_config=kafka_config,
        interval=pacing_config.interval_seconds,
    )

    try:
        worker.run()
    except KeyboardInterrupt:
        log.info("Shutting down pacing worker...")
        worker.stop()
