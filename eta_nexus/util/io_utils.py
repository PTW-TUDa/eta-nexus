from __future__ import annotations

import csv
import io
import json
import pathlib
import re
import sys
from collections.abc import Mapping, Sequence
from logging import getLogger
from typing import TYPE_CHECKING

import pandas as pd
import toml
import yaml

if TYPE_CHECKING:
    import types
    from collections.abc import Callable
    from typing import Any

    from typing_extensions import Self

    from eta_nexus.util.type_annotations import Path


log = getLogger(__name__)


def json_import(path: Path) -> list[Any] | dict[str, Any]:
    """Extend standard JSON import to allow '//' comments in JSON files.

    :param path: Path to JSON file.
    :return: Parsed dictionary.
    """
    path = pathlib.Path(path) if not isinstance(path, pathlib.Path) else path

    try:
        # Remove comments from the JSON file (using regular expression), then parse it into a dictionary
        cleanup = re.compile(r"^((?:(?:[^\/\"])*(?:\"[^\"]*\")*(?:\/[^\/])*)*)", re.MULTILINE)
        with path.open("r") as f:
            file = "\n".join(cleanup.findall(f.read()))
        result = json.loads(file)
        log.info(f"JSON file {path} loaded successfully.")
    except OSError as e:
        log.error(f"JSON file couldn't be loaded: {e.strerror}. Filename: {e.filename}")
        raise
    return result


def toml_import(path: Path) -> dict[str, Any]:
    """Import a TOML file and return the parsed dictionary.

    :param path: Path to TOML file.
    :return: Parsed dictionary.
    """
    path = pathlib.Path(path)

    try:
        with path.open("r") as f:
            result = toml.load(f)
        log.info(f"TOML file {path} loaded successfully.")
    except OSError as e:
        log.error(f"TOML file couldn't be loaded: {e.strerror}. Filename: {e.filename}")
        raise

    return result


def yaml_import(path: Path) -> dict[str, Any]:
    """Import a YAML file and return the parsed dictionary.

    :param path: Path to YAML file.
    :return: Parsed dictionary.
    """
    path = pathlib.Path(path)

    try:
        with path.open("r") as f:
            result = yaml.safe_load(f)
        log.info(f"YAML file {path} loaded successfully.")
    except OSError as e:
        log.error(f"YAML file couldn't be loaded: {e.strerror}. Filename: {e.filename}")
        raise

    return result


def load_config(file: Path) -> dict[str, Any]:
    """Load configuration from JSON, TOML, or YAML file.
    The read file is expected to contain a dictionary of configuration options.

    :param file: Path to the configuration file.
    :return: Dictionary of configuration options.
    """
    possible_extensions: dict[str, Callable] = {
        ".json": json_import,
        ".toml": toml_import,
        ".yml": yaml_import,
        ".yaml": yaml_import,
    }
    file_path = pathlib.Path(file)

    for extension, import_method in possible_extensions.items():
        _file_path: pathlib.Path = file_path.with_suffix(extension)
        if _file_path.exists():
            config = import_method(_file_path)
            break
    else:
        raise FileNotFoundError(f"Config file not found: {file}")

    if not isinstance(config, dict):
        raise TypeError(f"Config file {file} must define a dictionary of options.")

    return config


def replace_decimal_str(value: str | float, decimal: str = ".") -> str:
    """Replace the decimal sign in a string.

    :param value: The value to replace in.
    :param decimal: New decimal sign.
    """
    return str(value).replace(".", decimal)


def csv_export(
    path: Path,
    data: Mapping[str, Any] | Sequence[Mapping[str, Any] | Any] | pd.DataFrame,
    names: Sequence[str] | None = None,
    index: Sequence[int] | pd.DatetimeIndex | None = None,
    *,
    sep: str = ";",
    decimal: str = ".",
) -> None:
    """Export data to CSV file.

    :param path: Directory path to export data.
    :param data: Data to be saved.
    :param names: Field names used when data is a Matrix without column names.
    :param index: Optional sequence to set an index
    :param sep: Separator to use between the fields.
    :param decimal: Sign to use for decimal points.
    """
    _path = path if isinstance(path, pathlib.Path) else pathlib.Path(path)
    if _path.suffix != ".csv":
        _path.with_suffix(".csv")

    if isinstance(data, Mapping):
        with _path.open("a") as f:
            writer = csv.DictWriter(f, fieldnames=data.keys(), delimiter=sep)
            if not _path.exists():
                writer.writeheader()

            writer.writerow({key: replace_decimal_str(val, decimal) for key, val in data.items()})

    elif isinstance(data, pd.DataFrame):
        if index is not None:
            data.index = index
        data.to_csv(path_or_buf=str(_path), sep=sep, decimal=decimal)

    elif isinstance(data, Sequence):
        if names is not None:
            cols = names
        elif isinstance(data[-1], Mapping):
            cols = list(data[-1].keys())
        else:
            raise ValueError("Column names for csv export not specified.")

        _data = pd.DataFrame(data=data, columns=cols)
        if index is not None:
            _data.index = index
        _data.to_csv(path_or_buf=str(_path), sep=sep, decimal=decimal)

    log.info(f"Exported CSV data to {_path}.")


class Suppressor(io.TextIOBase):
    """Context manager to suppress standard output."""

    def __enter__(self) -> Self:
        self.stderr = sys.stderr
        sys.stderr = self
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: types.TracebackType | None
    ) -> None:
        sys.stderr = self.stderr
        if exc_type is not None:
            raise exc_type(exc_val).with_traceback(exc_tb)

    def write(self, x: Any) -> int:
        return 0
