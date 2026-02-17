from __future__ import annotations

import time
from typing import Any

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState


class QueryService:
    def __init__(self, warehouse_id: str, catalog: str, schema: str, table: str) -> None:
        self.warehouse_id = warehouse_id
        self.catalog = catalog
        self.schema = schema
        self.table = table
        self.client = WorkspaceClient()

    @property
    def fqtn(self) -> str:
        return f"{self.catalog}.{self.schema}.{self.table}"

    def _execute(self, statement: str) -> list[dict[str, Any]]:
        resp = self.client.statement_execution.execute_statement(
            warehouse_id=self.warehouse_id,
            statement=statement,
            wait_timeout="30s",
        )
        statement_id = resp.statement_id
        if not statement_id:
            return []

        while resp.status and resp.status.state in (
            StatementState.PENDING,
            StatementState.RUNNING,
        ):
            time.sleep(0.5)
            resp = self.client.statement_execution.get_statement(statement_id=statement_id)

        if not resp.status or resp.status.state != StatementState.SUCCEEDED:
            msg = resp.status.error.message if (resp.status and resp.status.error) else "statement failed"
            raise RuntimeError(msg)

        if not resp.result or not resp.result.data_array:
            return []
        schema = resp.manifest.schema
        names = [c.name for c in schema.columns]
        out: list[dict[str, Any]] = []
        for row in resp.result.data_array:
            out.append({names[i]: row[i] for i in range(min(len(names), len(row)))})
        return out

    def throughput(self, minutes: int) -> list[dict[str, Any]]:
        q = f"""
        SELECT
          date_trunc('minute', timestamp_micros(event_time)) AS minute_bucket,
          count(*) AS events
        FROM {self.fqtn}
        WHERE timestamp_micros(event_time) >= current_timestamp() - INTERVAL {minutes} MINUTES
        GROUP BY 1
        ORDER BY 1
        """
        return self._execute(q)

    def latency(self, minutes: int) -> list[dict[str, Any]]:
        q = f"""
        SELECT
          date_trunc('minute', timestamp_micros(event_time)) AS minute_bucket,
          avg((ingestion_timestamp - event_time) / 1000.0) AS avg_latency_ms,
          percentile_approx((ingestion_timestamp - event_time) / 1000.0, 0.95) AS p95_latency_ms,
          percentile_approx((ingestion_timestamp - event_time) / 1000.0, 0.99) AS p99_latency_ms
        FROM {self.fqtn}
        WHERE timestamp_micros(event_time) >= current_timestamp() - INTERVAL {minutes} MINUTES
        GROUP BY 1
        ORDER BY 1
        """
        return self._execute(q)

    def compression(self, minutes: int) -> list[dict[str, Any]]:
        q = f"""
        SELECT
          date_trunc('minute', timestamp_micros(event_time)) AS minute_bucket,
          avg(COALESCE(compression_ratio, 0.0)) AS avg_compression_ratio,
          avg(CASE WHEN COALESCE(sdt_compressed, false) THEN 1.0 ELSE 0.0 END) AS pct_sdt_flagged
        FROM {self.fqtn}
        WHERE timestamp_micros(event_time) >= current_timestamp() - INTERVAL {minutes} MINUTES
        GROUP BY 1
        ORDER BY 1
        """
        return self._execute(q)

