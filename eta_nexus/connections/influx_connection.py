"""
InfluxDB v3 SQL-backed connection for ETA Nexus.

This module provides :class:`InfluxConnection`, a concrete ``Connection`` that can
read latest values, read historic time series and write single/bulk time series
to InfluxDB v3 via the official ``influxdb-client-3`` pandas API.

Authentication is performed with an API token. You may pass it explicitly
via ``token=...`` or set the environment variable ``INFLUXDB3_AUTH_TOKEN``.
If neither is present, a final fallback to the base-connection password (``pwd``)
is attempted for convenience.
"""

from __future__ import annotations

import os
from datetime import timezone
from logging import getLogger
from typing import TYPE_CHECKING, Any, cast

import pandas as pd
from influxdb_client_3 import InfluxDBClient3

from eta_nexus.connections.connection import (
    Connection,
    SeriesReadable,
    SeriesWritable,
    StatusReadable,
    StatusWritable,
)
from eta_nexus.nodes import InfluxNode
from eta_nexus.util._influx_sql import build_latest_select, build_series_select

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from eta_nexus.util.type_annotations import Nodes, TimeStep


class InfluxConnection(
    Connection[InfluxNode],
    StatusReadable[InfluxNode],
    SeriesReadable[InfluxNode],
    StatusWritable[InfluxNode],
    SeriesWritable[InfluxNode],
    protocol="influx",
):
    """
    InfluxDB v3 connection using SQL+Pandas.

    Parameters (in addition to :class:`~eta_nexus.connections.connection.Connection`):
        database (str): Database (a.k.a. bucket) to connect to. If omitted, we try
            to infer from the first provided node or from ``INFLUXDB_DB``.
        token (str, optional): Auth token for InfluxDB v3. If omitted, we try
            ``INFLUXDB3_AUTH_TOKEN`` and finally ``pwd`` from the base connection.
    """

    logger = getLogger(__name__)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initialize the InfluxDB v3 client and validate required settings.

        Raises:
            ValueError: if ``database`` or authentication token cannot be resolved.
        """
        # --- PRE-RESOLVE database so base __init__ can use it in _extra_equality_key()
        db: str | None = kwargs.get("database")
        if not db:
            nodes = kwargs.get("nodes")
            if nodes:
                # nodes can be list/set; take the first
                first_node = next(iter(nodes))
                db = getattr(first_node, "database", None)
        if not db:
            db = os.getenv("INFLUXDB_DB")

        # Make it available during the base init:
        self.database = db  # may still be None; validate after super()

        super().__init__(*args, **kwargs)

        if self.database is None:
            raise ValueError(f"Database must be provided for {self.url_parsed.netloc}.")

        # Resolve token (kwarg > ENV > base pwd fallback)
        token: str | None = kwargs.get("token") or os.getenv("INFLUXDB3_AUTH_TOKEN") or self.pwd
        if not token:
            raise ValueError(
                "Missing InfluxDB auth token. Pass `token=...`, set INFLUXDB3_AUTH_TOKEN, "
                "or provide a `pwd` on the base connection."
            )

        self._client = InfluxDBClient3(
            host=self.url_parsed.geturl(),
            token=token,
            database=self.database,
        )

    def _group_by_table(self, nodes: set[InfluxNode]) -> dict[str, list[InfluxNode]]:
        """Group nodes by their target measurement/table name."""
        by_table: dict[str, list[InfluxNode]] = {}
        for n in nodes:
            by_table.setdefault(n.table, []).append(n)
        return by_table

    @classmethod
    def _from_node(
        cls, node: InfluxNode, usr: str | None = None, pwd: str | None = None, **kwargs: Any
    ) -> InfluxConnection:
        """Initialize from an :class:`InfluxNode` (implements Connection API)."""
        return super()._from_node(node, usr=usr, pwd=pwd, **kwargs)

    def _extra_equality_key(self) -> Any | None:
        """Include the database in equality/hash to distinguish same host different DBs."""
        return getattr(self, "database", None)

    # ---------- StatusReadable ----------
    def read(self, nodes: InfluxNode | Nodes[InfluxNode] | None = None) -> pd.DataFrame:
        """
        Read the *latest* value for each requested node.

        Returns:
            pd.DataFrame: Single-row DataFrame indexed by timestamp with one column per node field.
        """
        nodes_set = self._validate_nodes(nodes)
        by_table = self._group_by_table(nodes_set)

        frames: list[pd.DataFrame] = []
        for table, table_nodes in by_table.items():
            fields = [n.field for n in table_nodes]
            sql_statement = build_latest_select(table, fields)

            result_frame = self._client.query(query=sql_statement, language="sql", mode="pandas")
            if isinstance(result_frame, list):
                result_frame = pd.concat(result_frame, axis=1)
            if not result_frame.empty:
                result_frame = result_frame.set_index("time")

            frames.append(result_frame[[n.field for n in table_nodes]])

        out = pd.concat(frames, axis=1).sort_index() if frames else pd.DataFrame()
        # Keep requested column order
        return out[[n.field for n in nodes_set]]

    # ---------- SeriesReadable ----------
    def read_series(
        self,
        from_time: datetime,
        to_time: datetime,
        nodes: InfluxNode | Nodes[InfluxNode] | None = None,
        interval: TimeStep = 1,
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        Read historic series for each requested node over the partly-open interval
        ``[from_time, to_time)``. The *interval* parameter is currently accepted for
        API compatibility and may be used by backends that support server-side resampling.

        Returns:
            pd.DataFrame: Time-indexed frame with one column per node field.
        """

        nodes_set = self._validate_nodes(nodes)
        by_table = self._group_by_table(nodes_set)

        frames: list[pd.DataFrame] = []
        for table, table_nodes in by_table.items():
            fields = [n.field for n in table_nodes]

            # Convert to strict UTC 'Z' form expected by our helper
            start_iso_z = from_time.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            end_iso_z = to_time.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

            sql_statement = build_series_select(table, fields, start_iso_z, end_iso_z)

            result_frame = self._client.query(
                query=sql_statement,
                language="sql",
                mode="pandas",
            )
            if isinstance(result_frame, list):
                result_frame = pd.concat(result_frame, axis=1)
            if not result_frame.empty and "time" in result_frame.columns:
                result_frame = result_frame.set_index("time")

            frames.append(result_frame[[n.field for n in table_nodes]])

        out = pd.concat(frames, axis=1).sort_index() if frames else pd.DataFrame()
        # Column order by requested nodes
        return out[[n.field for n in nodes_set]]

    # ---------- StatusWritable ----------
    def write(self, values: Mapping[InfluxNode, Any]) -> None:
        """
        Write **current** values for the provided nodes.

        Groups by table/measurement and writes one row per table at the rounded current time.
        """
        if not values:
            return
        nodes_set = self._validate_nodes(set(values.keys()))
        by_table = self._group_by_table(nodes_set)

        now = self._assert_tz_awareness(self._round_timestamp(pd.Timestamp.utcnow().to_pydatetime(), 1))
        for table, table_nodes in by_table.items():
            row = {n.field: values[n] for n in table_nodes}
            write_frame = pd.DataFrame([row], index=[pd.to_datetime(now)])
            write_frame.index.name = "time"
            self._client.write(
                database=self.database,
                record=write_frame,
                data_frame_measurement_name=table,
            )

    # ---------- SeriesWritable ----------
    def write_series(
        self,
        values: Mapping[InfluxNode, pd.Series] | pd.DataFrame,
        *,
        allow_overwrite: bool = True,
        **kwargs: Any,
    ) -> None:
        """
        Write **historic** time series.

        Accepts either:
          - ``Mapping[InfluxNode, pd.Series]``: each Series must have a datetime-like index.
          - ``pd.DataFrame``: datetime-like index; columns must match node fields of ``selected_nodes``.

        Args:
            allow_overwrite: Currently forwarded to the underlying client if supported.
        """
        # --- DataFrame branch ---
        if isinstance(values, pd.DataFrame):
            if values.empty:
                return
            if not isinstance(values.index, pd.DatetimeIndex):
                raise TypeError("DataFrame index must be datetime-like.")

            nodes_set = self._validate_nodes(None)
            name_to_node = {n.field: n for n in nodes_set}
            unknown = [c for c in values.columns if c not in name_to_node]
            if unknown:
                raise ValueError(f"Columns not mapped to InfluxNodes: {unknown}")

            by_table_cols: dict[str, list[str]] = {}
            for c in values.columns:
                by_table_cols.setdefault(name_to_node[c].table, []).append(c)

            for table, cols in by_table_cols.items():
                write_frame = values[cols].copy()
                write_frame.index.name = "time"
                self._client.write(
                    database=self.database,
                    record=write_frame,
                    data_frame_measurement_name=table,
                )
            return

        # --- Mapping[InfluxNode, pd.Series] branch ---
        node_series_map = cast("Mapping[InfluxNode, pd.Series]", values)

        nodes = set(node_series_map.keys())
        nodes_set = self._validate_nodes(nodes)

        by_table_nodes: dict[str, list[InfluxNode]] = self._group_by_table(nodes_set)

        for table, table_nodes in by_table_nodes.items():
            aligned: list[pd.Series] = []
            for node in table_nodes:
                s = pd.Series(node_series_map[node])
                if not isinstance(s.index, pd.DatetimeIndex):
                    raise TypeError(f"Series for node '{node.name}' must have a datetime-like index.")
                aligned.append(s.sort_index().rename(node.field))

            write_frame = pd.concat(aligned, axis=1)
            write_frame.index.name = "time"
            self._client.write(
                database=self.database,
                record=write_frame,
                data_frame_measurement_name=table,
            )
