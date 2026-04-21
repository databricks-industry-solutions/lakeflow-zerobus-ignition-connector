from __future__ import annotations

from typing import Any

import psycopg


class PostgresQueryService:
    def __init__(self, dsn: str, table: str) -> None:
        self.dsn = dsn
        self.table = table

    def _execute(self, statement: str) -> list[dict[str, Any]]:
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(statement)
                rows = cur.fetchall()
                names = [d.name for d in cur.description] if cur.description else []
        return [{names[i]: row[i] for i in range(len(names))} for row in rows]

    def throughput(self, minutes: int) -> list[dict[str, Any]]:
        q = f"""
        SELECT
          date_trunc('minute', to_timestamp(event_time / 1000000.0)) AS minute_bucket,
          count(*) AS events
        FROM {self.table}
        WHERE to_timestamp(event_time / 1000000.0) >= now() - interval '{minutes} minutes'
        GROUP BY 1
        ORDER BY 1
        """
        return self._execute(q)

    def compression(self, minutes: int) -> list[dict[str, Any]]:
        q = f"""
        SELECT
          date_trunc('minute', to_timestamp(event_time / 1000000.0)) AS minute_bucket,
          avg(COALESCE(compression_ratio, 0.0)) AS avg_compression_ratio,
          avg(CASE WHEN COALESCE(sdt_compressed, false) THEN 1.0 ELSE 0.0 END) AS pct_sdt_flagged
        FROM {self.table}
        WHERE to_timestamp(event_time / 1000000.0) >= now() - interval '{minutes} minutes'
        GROUP BY 1
        ORDER BY 1
        """
        return self._execute(q)

