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
from dotenv import find_dotenv, load_dotenv

if TYPE_CHECKING:
    import types
    from collections.abc import Callable
    from typing import Any

    from eta_nexus.util.type_annotations import Path, Self


log = getLogger(__name__)

# Configuration file loaders by extension
_CONFIG_LOADERS: dict[str, Callable[[Path], list[Any] | dict[str, Any]]] = {
    ".json": lambda p: json_import(p),
    ".toml": lambda p: toml_import(p),
    ".yml": lambda p: yaml_import(p),
    ".yaml": lambda p: yaml_import(p),
}


def json_import(path: Path) -> list[Any] | dict[str, Any]:
    """Extend standard JSON import to allow '//' comments in JSON files.

    :param path: Path to JSON file.
    :return: Parsed dictionary.
    """
    path = pathlib.Path(path)

    try:
        # Remove comments from the JSON file (using regular expression), then parse it into a dictionary
        cleanup = re.compile(r"^((?:(?:[^\/\"])*(?:\"[^\"]*\")*(?:\/[^\/])*)*)", re.MULTILINE)
        with path.open("r", encoding="utf-8") as f:
            file = "\n".join(cleanup.findall(f.read()))
        result = json.loads(file)
        log.info(f"JSON file {path} loaded successfully.")
    except (OSError, json.JSONDecodeError):
        log.exception(f"Failed to load JSON file: {path}")
        raise
    return result


def toml_import(path: Path) -> dict[str, Any]:
    """Import a TOML file and return the parsed dictionary.

    :param path: Path to TOML file.
    :return: Parsed dictionary.
    """
    path = pathlib.Path(path)

    try:
        with path.open("r", encoding="utf-8") as f:
            result = toml.load(f)
        log.info(f"TOML file {path} loaded successfully.")
    except (OSError, Exception, toml.TomlDecodeError):
        log.exception(f"Failed to load TOML file: {path}")
        raise

    return result


def yaml_import(path: Path) -> dict[str, Any]:
    """Import a YAML file and return the parsed dictionary.

    :param path: Path to YAML file.
    :return: Parsed dictionary.
    """
    path = pathlib.Path(path)

    try:
        with path.open("r", encoding="utf-8") as f:
            result = yaml.safe_load(f)
        log.info(f"YAML file {path} loaded successfully.")
    except (OSError, yaml.YAMLError):
        log.exception(f"Failed to load YAML file: {path}")
        raise

    return result


def load_config(file: Path) -> dict[str, Any]:
    """Load configuration from JSON, TOML, or YAML file.

    The read file is expected to contain a dictionary of configuration options.
    When no file extension is provided, searches for files in the following priority order:
    1. JSON (.json)
    2. TOML (.toml)
    3. YAML (.yml, .yaml)

    :param file: Path to the configuration file (with or without extension).
    :return: Dictionary of configuration options.
    """
    file_path = pathlib.Path(file)

    # Case 1: Extension explicitly provided
    if file_path.suffix:
        loader = _CONFIG_LOADERS.get(file_path.suffix.lower())
        if loader is None:
            supported = ", ".join(sorted(_CONFIG_LOADERS.keys()))
            raise ValueError(f"Unsupported config file extension: {file_path.suffix}. Supported: {supported}")

        config_path = file_path

    # Case 2: No extension - search for supported formats
    else:
        config_path = None
        loader = None
        for extension, load_func in _CONFIG_LOADERS.items():
            candidate = file_path.with_suffix(extension)
            if candidate.exists():
                config_path = candidate
                loader = load_func
                break

        if config_path is None or loader is None:
            searched = [f"{file_path.absolute()}{ext}" for ext in _CONFIG_LOADERS]
            raise FileNotFoundError(f"Config file not found. Searched: {', '.join(searched)}")

    # Load and validate
    config = loader(config_path)  # type: ignore[arg-type] # config_path is guaranteed to be set here

    if not isinstance(config, dict):
        raise TypeError(f"Config file must contain a dictionary, got {type(config).__name__}: {config_path}")

    return config


def replace_decimal_str(value: str | float, decimal: str = ".") -> str:
    """Replace the decimal separator in a numeric string.

    :param value: The numeric value to convert.
    :param decimal: The decimal separator to use (e.g., '.' or ',').
    :return: String with replaced decimal separator.
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

    :param path: Path to export CSV data.
    :param data: Data to be saved (Mapping, DataFrame, or Sequence).
    :param names: Field names used when data is a sequence without column names.
    :param index: Optional sequence to set as the index.
    :param sep: Separator to use between fields.
    :param decimal: Decimal separator to use.
    """
    _path = pathlib.Path(path)
    if _path.suffix != ".csv":
        _path = _path.with_suffix(".csv")

    if isinstance(data, Mapping):
        file_exists = _path.exists()
        with _path.open("a", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=data.keys(), delimiter=sep)
            if not file_exists:
                writer.writeheader()

            writer.writerow({key: replace_decimal_str(val, decimal) for key, val in data.items()})

    elif isinstance(data, pd.DataFrame):
        if index is not None:
            data.index = index
        data.to_csv(path_or_buf=str(_path), sep=sep, decimal=decimal, encoding="utf-8")

    elif isinstance(data, Sequence) and not isinstance(data, (str, bytes)):
        if len(data) == 0:
            raise ValueError("Cannot export empty sequence to CSV.")

        if names is not None:
            cols = names
        elif isinstance(data[-1], Mapping):
            cols = list(data[-1].keys())
        else:
            raise ValueError("Column names for csv export not specified.")

        _data = pd.DataFrame(data=data, columns=cols)
        if index is not None:
            _data.index = index
        _data.to_csv(path_or_buf=str(_path), sep=sep, decimal=decimal, encoding="utf-8")

    log.info(f"Exported CSV data to {_path}.")


def autoload_env() -> None:
    """Load a .env file from the user's working directory by walking upward from there."""
    dotenv_path = find_dotenv(usecwd=True)
    load_dotenv(dotenv_path, override=False)


class Suppressor(io.TextIOBase):
    """Context manager to suppress standard error output (stderr)."""

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
