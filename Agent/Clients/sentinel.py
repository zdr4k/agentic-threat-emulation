"""
sentinel.py: runs KQL against the Log Analytics workspace and returns rows.

Auth via DefaultAzureCredential (az login, managed identity, or env vars).
Workspace customer id from SENTINEL_WORKSPACE_ID.
"""

from __future__ import annotations

import os
from datetime import timedelta

from azure.identity import DefaultAzureCredential
from azure.monitor.query import LogsQueryClient, LogsQueryStatus


class SentinelClient:
    def __init__(self, workspace_id: str | None = None):
        self.workspace_id = workspace_id or os.environ["SENTINEL_WORKSPACE_ID"]
        self._client = LogsQueryClient(DefaultAzureCredential())

    def query(self, kql: str, timespan_hours: int = 24) -> list[dict]:
        """Run a KQL query, return rows as dicts. Raises on a non-success status
        so a broken query never looks like empty results."""
        resp = self._client.query_workspace(
            workspace_id=self.workspace_id,
            query=kql,
            timespan=timedelta(hours=timespan_hours),
        )
        if resp.status != LogsQueryStatus.SUCCESS:
            raise RuntimeError(f"Sentinel query did not succeed: {resp.status}")

        rows: list[dict] = []
        for table in resp.tables:
            cols = table.columns
            for row in table.rows:
                rows.append(dict(zip(cols, row)))
        return rows

    def count(self, kql: str, timespan_hours: int = 24) -> int:
        """Run a query ending in | count and return the number."""
        rows = self.query(kql, timespan_hours=timespan_hours)
        if not rows:
            return 0
        return int(next(iter(rows[0].values())))