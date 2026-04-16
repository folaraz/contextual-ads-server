
import os
import sys
import logging
from typing import Any, Dict, Optional

import pandas as pd
import psycopg2
import psycopg2.extras

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PostgresConfig

logger = logging.getLogger(__name__)


class DashboardDB:
    """Manages a single psycopg2 connection for the dashboard."""

    def __init__(self, config: Optional[PostgresConfig] = None):
        self._config = config or PostgresConfig.from_env()
        self._conn: Optional[psycopg2.extensions.connection] = None

    def _get_conn(self) -> psycopg2.extensions.connection:
        """Return an open connection, reconnecting if necessary."""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(
                host=self._config.host,
                port=self._config.port,
                dbname=self._config.database,
                user=self._config.user,
                password=self._config.password,
                connect_timeout=5,
            )
            self._conn.autocommit = True
            logger.info(
                "Connected to PostgreSQL %s:%s/%s",
                self._config.host,
                self._config.port,
                self._config.database,
            )
        assert self._conn is not None
        return self._conn

    def close(self):
        if self._conn and not self._conn.closed:
            self._conn.close()

    def query_df(self, sql: str, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """Execute *sql* with named *params* and return a DataFrame."""
        try:
            conn = self._get_conn()
        except Exception as e:
            logger.error("Cannot connect to PostgreSQL: %s", e)
            return pd.DataFrame()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params or {})
                rows = cur.fetchall()
                if not rows:
                    return pd.DataFrame()
                return pd.DataFrame(rows)
        except Exception:
            # Reconnect on next call if something went wrong
            try:
                if self._conn and not self._conn.closed:
                    self._conn.close()
            except Exception:
                pass
            self._conn = None
            raise

    def execute(self, sql: str, params: Optional[Dict[str, Any]] = None) -> None:
        """Execute a statement that does not return rows."""
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(sql, params or {})


    def refresh_materialized_views(self) -> None:
        """Refresh the ads_analytics materialized views so KPIs are fresh."""
        try:
            self.execute("SELECT ads_analytics.refresh_materialized_views();")
            logger.info("Materialized views refreshed")
        except Exception as e:
            logger.warning("Could not refresh materialized views: %s", e)



