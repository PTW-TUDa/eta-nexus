# ruff: noqa: S608
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

# Accept: letters, digits, underscore; start with letter/underscore
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Strict UTC timestamp with optional microseconds, ending with 'Z'
_TS_UTC_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")


def _quote_ident(name: str) -> str:
    """Validate and double-quote a SQL identifier (table/column)."""
    if not _IDENT_RE.fullmatch(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return f'"{name}"'


def ident_list_sql(idents: Iterable[str]) -> str:
    """Comma-separated, validated, quoted identifiers."""
    return ", ".join(_quote_ident(i) for i in idents)


def table_sql(table_name: str) -> str:
    return _quote_ident(table_name)


def _ts_lit(ts_utc_z: str) -> str:
    """Validate a UTC 'Z' ISO-8601 string; return as-is (for TIMESTAMP '...')."""
    if not _TS_UTC_RE.fullmatch(ts_utc_z):
        raise ValueError(f"Invalid UTC timestamp literal: {ts_utc_z!r}")
    return ts_utc_z


def build_latest_select(table_name: str, fields: Iterable[str]) -> str:
    """SELECT last row for the given fields."""
    return "SELECT time, " + ident_list_sql(fields) + " FROM " + table_sql(table_name) + " ORDER BY time DESC LIMIT 1"


def build_series_select(
    table_name: str,
    fields: Iterable[str],
    start_utc_z: str,
    end_utc_z: str,
) -> str:
    """SELECT time series between two UTC 'Z' timestamps (literals)."""
    return (
        "SELECT time, "
        + ident_list_sql(fields)
        + " FROM "
        + table_sql(table_name)
        + " WHERE time >= TIMESTAMP '"
        + _ts_lit(start_utc_z)
        + "' AND time <= TIMESTAMP '"
        + _ts_lit(end_utc_z)
        + "' ORDER BY time ASC"
    )
