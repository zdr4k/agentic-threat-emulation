
# Clients/sentinel.py

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from azure.identity import DefaultAzureCredential
from azure.monitor.query import LogsQueryClient, LogsQueryStatus
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the Agent directory
ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_PATH)

class SentinelClient:
    def __init__(self, workspace_id: str | None = None):
        self.workspace_id = (
            workspace_id or os.environ["SENTINEL_WORKSPACE_ID"]
        )

        self._client = LogsQueryClient(
            DefaultAzureCredential(
                exclude_interactive_browser_credential=True
            )
        )

    @staticmethod
    def _rows(response) -> list[dict]:
        if response.status != LogsQueryStatus.SUCCESS:
            raise RuntimeError(
                f"Log Analytics query failed: {response.status}"
            )

        result = []

        for table in response.tables:
            columns = [
                col if isinstance(col, str) else col.name
                for col in table.columns
            ]

            for row in table.rows:
                result.append(dict(zip(columns, row)))

        return result

    def query(
        self,
        kql: str,
        timespan_hours: int = 24,
    ) -> list[dict]:
        if timespan_hours <= 0:
            raise ValueError("timespan_hours must be positive")

        response = self._client.query_workspace(
            workspace_id=self.workspace_id,
            query=kql,
            timespan=timedelta(hours=timespan_hours),
            server_timeout=60,
        )

        return self._rows(response)

    def query_range(
        self,
        kql: str,
        start: datetime,
        end: datetime,
    ) -> list[dict]:
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("Start and end must be timezone-aware")

        start = start.astimezone(timezone.utc)
        end = end.astimezone(timezone.utc)

        if end <= start:
            raise ValueError("End must be after start")

        response = self._client.query_workspace(
            workspace_id=self.workspace_id,
            query=kql,
            timespan=(start, end),
            server_timeout=60,
        )

        return self._rows(response)

    def count(
        self,
        kql: str,
        timespan_hours: int = 24,
    ) -> int:
        rows = self.query(kql, timespan_hours)

        if not rows:
            return 0

        return int(next(iter(rows[0].values())))
