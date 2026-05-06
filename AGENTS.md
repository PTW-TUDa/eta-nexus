# AGENTS.md

Codex guidance for this repository.

- Package: `eta-nexus`, a Python library for standardized industrial/API connectivity.
- Source: `eta_nexus/`; tests: `test/`; docs: `docs/`; examples: `examples/`.
- Build/deps: Poetry 2.x via `pyproject.toml` and `poetry.lock`.
- Python: `>=3.10.16,<3.13.0`.
- Typed package: keep `eta_nexus/py.typed` and public type hints accurate.

## Architecture

- `eta_nexus/nodes/node.py`
  - `Node` is the immutable attrs-based data-point abstraction.
  - Protocol nodes live in `eta_nexus/nodes/*_node.py`.
  - Register nodes with `class XNode(Node, protocol="<protocol>")`.

- `eta_nexus/connections/connection.py`
  - `Connection` is the base client abstraction.
  - Create clients with `Connection.from_node()` / `Connection.from_nodes()`.
  - Register clients with `class XConnection(..., protocol="<protocol>")`.

- Connection capabilities:
  - `StatusReadable.read()`
  - `StatusWritable.write()`
  - `StatusSubscribable.subscribe()`
  - `SeriesReadable.read_series()`
  - `SeriesWritable.write_series()`
  - `SeriesSubscribable.subscribe_series()`

- `RESTConnection`
  - Base for REST/API connectors.
  - Reuse its cached sessions, retries, auth hooks, `_raw_request()`, and parsing hooks.
  - REST/API connectors include ENTSO-E, Forecast.Solar, Wetterdienst, SMARD, EnEffCo.

- `eta_nexus/connection_manager.py`
  - Loads config, creates nodes/connections, manages init/activate/deactivate/close.
  - Main control method: `ConnectionManager.step()`.

- Other subsystems:
  - Servers: `eta_nexus/servers/opcua_server.py`, `eta_nexus/servers/modbus_server.py`.
  - Subscriptions: `eta_nexus/subscription_handlers/`.
  - Timeseries helpers: `eta_nexus/timeseries/dataframes.py`.

## Key Folders

- `eta_nexus/connections/`: protocol implementations.
- `eta_nexus/nodes/`: node classes and config parsing.
- `test/test_connections/`: protocol tests and VCR cassettes.
- `test/test_nodes/`: node tests.
- `test/test_servers/`: server tests.
- `test/test_timeseries/`: dataframe utility tests.
- `test/resources/`: sample files and config fixtures.
- `docs/connections/`: connector docs.
- `.gitlab-ci.yml`: CI workflow source of truth.

## Commands

- Install/update deps: `poetry sync`
- Install hooks: `poetry run pre-commit install`
- Run all tests: `poetry run pytest`
- Parallel tests: `poetry run pytest -n auto`
- CI-style parallel tests: `poetry run pytest -n logical --dist loadscope --record-mode=none`
- Coverage: `poetry run pytest --cov`
- Coverage report: `poetry run coverage report`
- Coverage HTML: `poetry run coverage html`
- Lint: `poetry run ruff check`
- Lint fix: `poetry run ruff check --fix`
- Format: `poetry run ruff format`
- Type check: `poetry run mypy --config-file pyproject.toml`
- Spelling: `poetry run codespell`
- Package check: `poetry check`
- Docs build: `cd docs` then `poetry run make html`

## Workflows

- Add a protocol:
  - Add `eta_nexus/nodes/<protocol>_node.py`.
  - Add `eta_nexus/connections/<protocol>_connection.py`.
  - Export from `eta_nexus/nodes/__init__.py` and `eta_nexus/connections/__init__.py`.
  - Add docs in `docs/connections/`.
  - Add tests in `test/test_nodes/` and `test/test_connections/`.

- Change REST behavior:
  - Prefer `RESTConnection` hooks over duplicate request/session code.
  - Implement `_initialize_session()`, `_parse_response()`, and `read_node()` where needed.
  - Return `pandas.DataFrame` with node names as columns.

- Change `ConnectionManager`:
  - Edit `eta_nexus/connection_manager.py`.
  - Preserve JSON/YAML/TOML config compatibility via `eta_nexus/util/io_utils.py`.
  - Add fixtures under `test/resources/connection_manager/`.

- Change timeseries helpers:
  - Edit `eta_nexus/timeseries/dataframes.py`.
  - Add focused tests in `test/test_timeseries/`.

- Change docs:
  - Edit `.rst` files under `docs/`.
  - Verify with `cd docs` then `poetry run make html`.

## Testing Rules

- Prefer targeted tests before broad runs:
  - `poetry run pytest test/test_nodes`
  - `poetry run pytest test/test_connections/test_<protocol>.py`
  - `poetry run pytest test/test_timeseries`
- For broad changes, run `poetry run pytest -n logical --dist loadscope --record-mode=none`.
- Use VCR cassettes under `test/test_connections/cassettes/` for API tests.
- Do not depend on live network unless the test is explicitly marked `live`.
- Keep tests deterministic with fixed timestamps and `test/resources/` files.

## Style Rules

- Follow existing attrs-based node patterns.
- Keep protocol strings consistent across nodes, connections, docs, and tests.
- Use pandas-native APIs for dataframe/time-series work.
- Use existing config loaders, not ad-hoc JSON/YAML/TOML parsing.
- Do not add runtime dependencies unless necessary and reflected in `pyproject.toml`.
