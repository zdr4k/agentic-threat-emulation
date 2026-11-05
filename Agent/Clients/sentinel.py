
"""
Sentinel client: read-only KQL queries against Log Analytics.

Authentication: DefaultAzureCredential.
Workspace: SENTINEL_WORKSPACE_ID.
"""

from __future__ import annotations

import os
from datetime import timedelta

from azure.identity import DefaultAzureCredential
from azure.monitor.query import LogsQueryClient, LogsQueryStatus


class SentinelClient:
    def __init__(self, workspace_id: str | None = None):
        self.workspace_id = (
            workspace_id or os.environ["SENTINEL_WORKSPACE_ID"]
        )

        self._client = LogsQueryClient(
            credential=DefaultAzureCredential(
                exclude_interactive_browser_credential=True
            )
        )

    def query(
        self,
        kql: str,
        timespan_hours: int = 24,
    ) -> list[dict]:
        """Execute KQL and return rows as dictionaries."""

        if not kql.strip():
            raise ValueError("KQL query cannot be empty")

        if not 1 <= timespan_hours <= 168:
            raise ValueError("Timespan must be between 1 and 168 hours")

        response = self._client.query_workspace(
            workspace_id=self.workspace_id,
            query=kql,
            timespan=timedelta(hours=timespan_hours),
            server_timeout=60,
        )

        if response.status != LogsQueryStatus.SUCCESS:
            raise RuntimeError(
                f"Sentinel query failed: {response.status}"
            )

        rows = []

        for table in response.tables:
            columns = [
                col if isinstance(col, str) else col.name
                for col in table.columns
            ]

            for row in table.rows:
                rows.append(dict(zip(columns, row)))

        return rows

    def count(self, kql: str, timespan_hours: int = 24) -> int:
        """Return the first numeric value of a count query."""

        rows = self.query(kql, timespan_hours)

        if not rows:
            return 0

        return int(next(iter(rows[0].values())))
