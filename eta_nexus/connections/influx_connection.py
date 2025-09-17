from __future__ import annotations

import os
from datetime import timezone
from typing import TYPE_CHECKING, Any, cast

import pandas as pd
from influxdb_client_3 import InfluxDBClient3

from eta_nexus.connections.connection import (
    Connection,
    Readable,
    SeriesReadable,
    SeriesWritable,
    Writable,
)
from eta_nexus.nodes import InfluxNode
from eta_nexus.util._influx_sql import build_latest_select, build_series_select

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from eta_nexus.util.type_annotations import Nodes, TimeStep


class InfluxConnection(
    Connection[InfluxNode],
    Readable[InfluxNode],
    SeriesReadable[InfluxNode],
    Writable[InfluxNode],
    SeriesWritable[InfluxNode],
    protocol="influx",
):
    """
    Async wrapper around InfluxDBClient for reading and writing single points or time series via pandas.
    Configured via environment variables: INFLUXDB_HOST, INFLUXDB_PORT, INFLUXDB_USER, INFLUXDB_PASS, INFLUXDB_DB.

    :param url: Inherited from Connection.
    :param usr: Inherited from Connection.
    :param pwd: Inherited from Connection.
    :param nodes: Inherited from Connection.
    :param database: The database name to connect to.

    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.database = kwargs.get("database")
        if not self.database:
            nodes = kwargs.get("nodes")
            if nodes:
                self.database = nodes[0].database
        if self.database is None:
            raise ValueError(f"Database must be provided for {self.url_parsed.netloc}.")

        # Store a clear host string; underlying base already parsed URL for us
        self.host = self.url_parsed.geturl()

        self._client = InfluxDBClient3(
            host=self.url_parsed.geturl(),
            token=os.getenv("INFLUXDB3_AUTH_TOKEN"),
            database=self.database,
        )

    def _group_by_table(self, nodes: set[InfluxNode]) -> dict[str, list[InfluxNode]]:
        by_table: dict[str, list[InfluxNode]] = {}
        for n in nodes:
            by_table.setdefault(n.table, []).append(n)
        return by_table

    @classmethod
    def _from_node(
        cls, node: InfluxNode, usr: str | None = None, pwd: str | None = None, **kwargs: Any
    ) -> InfluxConnection:
        """Initialize the connection object from an Influx protocol node object.

        :param node: Node to initialize from.
        :param usr: Username to use.
        :param pwd: Password to use.
        :return: InfluxConnection object.
        """
        return super()._from_node(node, usr=usr, pwd=pwd, **kwargs)

    def _extra_equality_key(self) -> Any | None:
        """Adds database to equality check."""
        return self.database

    # ---------- Readable ----------
    def read(self, nodes: InfluxNode | Nodes[InfluxNode] | None = None) -> pd.DataFrame:
        """Return the latest values for the requested nodes as a single-row DataFrame."""
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
        """Read historic series for the requested nodes."""
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

    # ---------- Writable ----------
    def write(self, values: Mapping[InfluxNode, Any]) -> None:
        """Write **current** values. Groups by table and writes one row per table at 'now'."""
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
        Write historic series.

        - Mapping[Node -> Series]: each Series index must be datetime-like
        - DataFrame: index must be datetime-like; columns must match node names of `selected_nodes`
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
