import json
import logging
import os
import pathlib
import sys
import textwrap
from datetime import datetime, timezone

import pandas as pd
import pytest
import toml
import yaml
from dateutil import tz

from eta_nexus.util import (
    SelfsignedKeyCertPair,
    dict_search,
    load_config,
    log_add_filehandler,
    round_timestamp,
)
from eta_nexus.util.io_utils import (
    Suppressor,
    autoload_env,
    csv_export,
    json_import,
    replace_decimal_str,
    toml_import,
    yaml_import,
)


class TestLoadConfig:
    """Tests for load_config function."""

    def test_from_config(self, config_connection_manager) -> None:
        """Test loading config from all supported formats.

        Uses config_connection_manager fixture from conftest.py.
        """
        file = pathlib.Path(config_connection_manager["file"])

        config_json = load_config(file.with_suffix(".json"))
        config_toml = load_config(file.with_suffix(".toml"))
        config_yaml = load_config(file.with_suffix(".yaml"))

        assert config_json == config_toml == config_yaml

    def test_respects_explicit_extension(self, tmp_path: pathlib.Path):
        """
        If a path with an extension is given, load that file ONLY,
        even if siblings with other extensions exist.
        """

        (tmp_path / "config.json").write_text(json.dumps({"a": 2}))
        (tmp_path / "config.toml").write_text("a = 3")
        (tmp_path / "config.yaml").write_text("a: 1")

        out = load_config(tmp_path / "config.yaml")
        assert out == {"a": 1}

    def test_without_extension_searches_known_types(self, tmp_path: pathlib.Path):
        """
        If no extension is provided, the loader should search known extensions.
        Here we only create TOML to make the behavior unambiguous.
        """
        (tmp_path / "config.toml").write_text("a = 42")

        out = load_config(tmp_path / "config")  # no suffix
        assert out == {"a": 42}

    def test_unsupported_extension_raises(self, tmp_path: pathlib.Path):
        (tmp_path / "settings.ini").write_text("[section]\na=1\n")
        with pytest.raises(ValueError, match=r"(?i)(unsupported|unknown).*(ext|extension|file type)"):
            load_config(tmp_path / "settings.ini")

    def test_non_mapping_raises(self, tmp_path: pathlib.Path):
        # YAML list instead of dict
        (tmp_path / "list.yaml").write_text(
            textwrap.dedent("""\
            - 1
            - 2
        """)
        )
        with pytest.raises(TypeError, match="dict"):
            load_config(tmp_path / "list.yaml")

    def test_no_file_found_raises(self, tmp_path: pathlib.Path):
        """
        When no config file exists with any supported extension,
        should raise FileNotFoundError with searched paths.
        """
        with pytest.raises(FileNotFoundError, match=r"Config file not found"):
            load_config(tmp_path / "nonexistent")

    @pytest.mark.parametrize(
        ("filename", "content", "expected"),
        [
            ("config.JSON", '{"source": "json"}', {"source": "json"}),
            ("config.Toml", 'source = "toml"', {"source": "toml"}),
            ("config.YAML", "source: yaml", {"source": "yaml"}),
            ("config.YML", "source: yml", {"source": "yml"}),
        ],
    )
    def test_case_insensitive_extension(
        self, tmp_path: pathlib.Path, filename: str, content: str, expected: dict
    ) -> None:
        """
        Extensions should work regardless of case (.JSON, .Toml, .YAML).
        """
        (tmp_path / filename).write_text(content)
        assert load_config(tmp_path / filename) == expected

    def test_priority_order(self, tmp_path: pathlib.Path):
        """
        When no extension is given and multiple config files exist,
        JSON should be preferred over TOML, which is preferred over YAML.
        """
        (tmp_path / "config.json").write_text(json.dumps({"source": "json"}))
        (tmp_path / "config.toml").write_text('source = "toml"')
        (tmp_path / "config.yaml").write_text("source: yaml")

        out = load_config(tmp_path / "config")
        assert out == {"source": "json"}, "JSON should have priority over TOML and YAML"

    def test_accepts_string_path(self, tmp_path: pathlib.Path):
        """
        Should accept string paths in addition to Path objects.
        """
        (tmp_path / "config.json").write_text(json.dumps({"key": "value"}))
        out = load_config(str(tmp_path / "config.json"))
        assert out == {"key": "value"}

    def test_error_shows_searched_paths(self, tmp_path: pathlib.Path):
        """
        FileNotFoundError should indicate which paths were searched.
        """
        config_base = tmp_path / "missing"
        with pytest.raises(FileNotFoundError) as exc_info:
            load_config(config_base)

        error_msg = str(exc_info.value)
        assert "Searched:" in error_msg
        # Should mention at least one of the attempted extensions
        assert any(ext in error_msg for ext in [".json", ".toml", ".yaml", ".yml"])

    def test_malformed_json_raises(self, tmp_path: pathlib.Path):
        """
        Should propagate JSON parsing errors for malformed JSON.
        """
        (tmp_path / "bad.json").write_text("{invalid json}")
        with pytest.raises(json.JSONDecodeError):
            load_config(tmp_path / "bad.json")


def test_log_file_handler(tmp_path: pathlib.Path) -> None:
    log_path = tmp_path / "test_log.log"
    log = log_add_filehandler(log_path, level=3)
    try:
        log.info("Info")
        log.error("Error")

        log_content = log_path.read_text()

        assert "Info" not in log_content
        assert "Error" in log_content
    finally:
        logging.shutdown()
        log.handlers.clear()


def test_log_file_handler_no_path(caplog) -> None:
    log = log_add_filehandler(None, level=3)
    try:
        assert "No filename specified for filehandler. Using default filename eta_nexus" in caplog.text
        assert "eta_nexus" in log.handlers[-1].baseFilename
    finally:
        log_file = pathlib.Path(log.handlers[-1].baseFilename)
        logging.shutdown()
        log.handlers.clear()
        if log_file.exists():
            log_file.unlink()


@pytest.mark.parametrize(
    ("datetime_str", "interval", "expected"),
    [
        ("2016-01-01T02:02:02", 1, "2016-01-01T02:02:02"),
        ("2016-01-01T02:02:02", 60, "2016-01-01T02:03:00"),
        ("2016-01-01T02:02:00", 60, "2016-01-01T02:02:00"),
        ("2016-01-01T02:02:02", 60 * 60, "2016-01-01T03:00:00"),
        ("2016-01-01T02:00:00", 60 * 60, "2016-01-01T02:00:00"),
    ],
)
def test_round_timestamp(datetime_str, interval, expected):
    dt = datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S")

    result = round_timestamp(dt, interval, ensure_tz=False).isoformat(sep="T", timespec="seconds")

    assert result == expected


@pytest.mark.parametrize(
    ("datetime_str", "interval", "timezone", "expected", "expected_timezone"),
    [
        ("2016-01-01T02:02:02", 1, None, "2016-01-01T02:02:02", tz.tzlocal()),
        ("2016-01-01T02:02:02", 1, timezone.utc, "2016-01-01T02:02:02", timezone.utc),
        ("2016-01-01T02:02:02", 60, timezone.utc, "2016-01-01T02:03:00", timezone.utc),
        ("2016-01-01T02:02:02", 60 * 60, timezone.utc, "2016-01-01T03:00:00", timezone.utc),
    ],
)
def test_round_timestamp_with_timezone(datetime_str, interval, timezone, expected, expected_timezone):
    """Check if datetime object has the correct timezone after rounding"""
    dt = datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone)
    dt_expected = datetime.strptime(expected, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=expected_timezone)

    result = round_timestamp(dt, interval)

    assert result == dt_expected


def test_dict_search():
    assert dict_search({"key": "value"}, "value") == "key"


def test_dict_search_fail():
    with pytest.raises(ValueError, match=r".*not specified in specified dictionary"):
        dict_search({}, "value")


def test_selfsignedkeycertpair_empty():
    with SelfsignedKeyCertPair("opc_client").tempfiles() as tempfiles:
        assert tempfiles is not None


def test_selfsignedkeycertpair():
    keycert_pair = SelfsignedKeyCertPair(
        common_name="opc_client",
        country="DE",
        province="HE",
        city="Darmstadt",
        organization="TU Darmstadt",
    )
    with keycert_pair.tempfiles() as tempfiles:
        assert tempfiles is not None


def test_selfsignedkeycertpair_fail() -> None:
    with pytest.raises(ValueError, match=r".*length must be >= 2 and <= 2, but it.*"):
        SelfsignedKeyCertPair(
            common_name="opc_client",
            country="DEUTSCHLAND",
            province="HESSEN",
            city="Darmstadt",
            organization="TU Darmstadt",
        )


class TestReplaceDecimalStr:
    """Tests for replace_decimal_str function."""

    @pytest.mark.parametrize(
        ("value", "decimal", "expected"),
        [
            (3.14159, ",", "3,14159"),  # European comma notation
            ("3.14159", ",", "3,14159"),  # String input
            (42, ",", "42"),  # Integer (unchanged - no decimal point)
            (-123.456, ",", "-123,456"),  # Negative float
        ],
    )
    def test_decimal_replacement(self, value: str | float, decimal: str, expected: str) -> None:
        """Test decimal separator replacement with various inputs."""
        assert replace_decimal_str(value, decimal) == expected


class TestCsvExport:
    """Tests for csv_export function."""

    def test_export_mapping(self, tmp_path: pathlib.Path) -> None:
        """Export a single dict row to CSV."""
        csv_file = tmp_path / "output.csv"
        data = {"name": "Alice", "score": 95.5}

        csv_export(csv_file, data, sep=";", decimal=".")

        content = csv_file.read_text(encoding="utf-8")
        lines = content.strip().split("\n")
        assert len(lines) == 2, "Should have header + 1 data row"
        assert "name" in lines[0]
        assert "score" in lines[0]
        assert "Alice" in lines[1]
        assert "95.5" in lines[1]

    def test_export_mapping_append(self, tmp_path: pathlib.Path) -> None:
        """Multiple dict exports should append rows without repeating headers."""
        csv_file = tmp_path / "output.csv"
        csv_export(csv_file, {"a": 1, "b": 2})
        csv_export(csv_file, {"a": 3, "b": 4})

        content = csv_file.read_text(encoding="utf-8")
        lines = content.strip().split("\n")
        assert len(lines) == 3, "Should have 1 header + 2 data rows"
        # Header should appear only once
        assert content.count("a;b") == 1

    def test_export_dataframe(self, tmp_path: pathlib.Path) -> None:
        """Export a pandas DataFrame to CSV."""
        csv_file = tmp_path / "df_output.csv"
        data_frame = pd.DataFrame({"col1": [1, 2, 3], "col2": [4.5, 5.5, 6.5]})

        csv_export(csv_file, data_frame, sep=",", decimal=".")

        content = csv_file.read_text(encoding="utf-8")
        assert "col1" in content
        assert "col2" in content
        assert "4.5" in content

    def test_export_sequence_of_mappings(self, tmp_path: pathlib.Path) -> None:
        """Export a list of dicts to CSV."""
        csv_file = tmp_path / "seq_output.csv"
        data = [{"x": 1, "y": 2}, {"x": 3, "y": 4}, {"x": 5, "y": 6}]

        csv_export(csv_file, data)

        content = csv_file.read_text(encoding="utf-8")
        lines = content.strip().split("\n")
        # Header + index header + 3 data rows
        assert len(lines) >= 4

    def test_export_sequence_with_names(self, tmp_path: pathlib.Path) -> None:
        """Export sequence of values with explicit column names."""
        csv_file = tmp_path / "named_seq.csv"
        data = [[1, 2], [3, 4], [5, 6]]

        csv_export(csv_file, data, names=["col_a", "col_b"])

        content = csv_file.read_text(encoding="utf-8")
        assert "col_a" in content
        assert "col_b" in content

    def test_export_empty_sequence_raises(self, tmp_path: pathlib.Path) -> None:
        """Empty sequence should raise ValueError."""
        csv_file = tmp_path / "empty.csv"
        with pytest.raises(ValueError, match=r"Cannot export empty sequence"):
            csv_export(csv_file, [])

    def test_export_sequence_without_names_raises(self, tmp_path: pathlib.Path) -> None:
        """Sequence of non-mappings without names should raise ValueError."""
        csv_file = tmp_path / "no_names.csv"
        with pytest.raises(ValueError, match=r"Column names.*not specified"):
            csv_export(csv_file, [[1, 2], [3, 4]])

    def test_auto_adds_csv_extension(self, tmp_path: pathlib.Path) -> None:
        """Should automatically add .csv extension if missing."""
        csv_file = tmp_path / "no_extension"  # No .csv suffix
        csv_export(csv_file, {"a": 1})

        assert (tmp_path / "no_extension.csv").exists()
        assert not (tmp_path / "no_extension").exists()

    def test_path_not_mutated(self, tmp_path: pathlib.Path) -> None:
        """Original path variable should not be modified."""
        original_path = tmp_path / "test"
        path_copy = pathlib.Path(original_path)  # Keep reference

        csv_export(original_path, {"key": "value"})

        # The function should create test.csv, but original_path should be unchanged
        assert str(path_copy) == str(original_path)


class TestAutoloadEnv:
    """Tests for autoload_env function."""

    def test_loads_dotenv_file(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should load variables from .env file in working directory."""
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_AUTOLOAD_VAR=hello_world\n")

        # Change to temp directory
        monkeypatch.chdir(tmp_path)
        # Remove var if it exists
        monkeypatch.delenv("TEST_AUTOLOAD_VAR", raising=False)

        autoload_env()

        assert os.environ.get("TEST_AUTOLOAD_VAR") == "hello_world"

    def test_does_not_override_existing(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should not override existing environment variables (override=False)."""
        env_file = tmp_path / ".env"
        env_file.write_text("EXISTING_VAR=from_dotenv\n")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("EXISTING_VAR", "original_value")

        autoload_env()

        assert os.environ.get("EXISTING_VAR") == "original_value"

    def test_handles_missing_dotenv(self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should not raise error if no .env file exists."""
        monkeypatch.chdir(tmp_path)
        # No .env file created

        # Should not raise
        autoload_env()


class TestSuppressor:
    """Tests for Suppressor context manager."""

    def test_suppresses_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Should suppress stderr output within context."""
        with Suppressor():
            sys.stderr.write("This should be suppressed\n")

        captured = capsys.readouterr()
        assert "suppressed" not in captured.err

    def test_restores_stderr(self) -> None:
        """Should restore original stderr after exiting context."""
        original_stderr = sys.stderr

        with Suppressor():
            assert sys.stderr is not original_stderr

        assert sys.stderr is original_stderr

    def test_propagates_exceptions_and_restores_stderr(self) -> None:
        """Should re-raise exceptions and restore stderr after exception."""
        original_stderr = sys.stderr

        with pytest.raises(RuntimeError, match="test error"):
            with Suppressor():
                raise RuntimeError("test error")

        assert sys.stderr is original_stderr


class TestJsonImport:
    """Tests for json_import function."""

    def test_loads_valid_json(self, tmp_path: pathlib.Path) -> None:
        """Should load valid JSON file."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"key": "value", "number": 42}')

        result = json_import(json_file)

        assert result == {"key": "value", "number": 42}

    def test_supports_comments(self, tmp_path: pathlib.Path) -> None:
        """Should support // style comments in JSON."""
        json_file = tmp_path / "commented.json"
        json_file.write_text(
            textwrap.dedent("""\
            {
                // This is a comment
                "key": "value",
                "number": 123 // inline comment
            }
        """)
        )

        result = json_import(json_file)

        assert result == {"key": "value", "number": 123}

    def test_returns_list_for_json_array(self, tmp_path: pathlib.Path) -> None:
        """Should return list when JSON root is an array."""
        json_file = tmp_path / "array.json"
        json_file.write_text('[1, 2, 3, "four"]')

        result = json_import(json_file)

        assert result == [1, 2, 3, "four"]
        assert isinstance(result, list)


class TestTomlImport:
    """Tests for toml_import function."""

    def test_malformed_toml_raises(self, tmp_path: pathlib.Path) -> None:
        """Should raise TomlDecodeError for malformed TOML."""
        toml_file = tmp_path / "bad.toml"
        toml_file.write_text("[unclosed section")

        with pytest.raises(toml.TomlDecodeError):
            toml_import(toml_file)


class TestYamlImport:
    """Tests for yaml_import function."""

    def test_malformed_yaml_raises(self, tmp_path: pathlib.Path) -> None:
        """Should raise YAMLError for malformed YAML."""
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("key: [unclosed bracket")

        with pytest.raises(yaml.YAMLError):
            yaml_import(yaml_file)
