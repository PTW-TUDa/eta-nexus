import asyncio
import concurrent.futures
import logging
import pathlib
import random
import shutil
import socket

import pytest


def get_free_port():
    """Find an available port dynamically."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("", 0))
        return s.getsockname()[1]


@pytest.fixture(autouse=True, scope="session")
def _silence_logging():
    logging.root.setLevel(logging.ERROR)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    # Check for the disable_logging marker
    root_level = logging.CRITICAL if "disable_logging" in item.keywords else logging.NOTSET
    # Set logging level to INFO if caplog is used
    eta_nexus_level = logging.INFO if "caplog" in item.fixturenames else logging.ERROR

    # Set disable logging level for root logger
    logging.disable(root_level)
    # Set logger level for "eta_nexus" namespace
    logging.getLogger("eta_nexus").setLevel(eta_nexus_level)


@pytest.fixture(scope="session")
def temp_dir():
    while True:
        temp_dir = pathlib.Path.cwd() / f"tmp_{random.randint(10000, 99999)}"
        try:
            temp_dir.mkdir(exist_ok=False)
        except FileExistsError:
            continue
        else:
            break

    yield temp_dir
    shutil.rmtree(temp_dir)


async def stop_execution(sleep_time):
    await asyncio.sleep(sleep_time)


@pytest.fixture(scope="module")
def config_modbus_port():
    """Dynamic port for Modbus server - module scoped for isolation."""
    return get_free_port()


@pytest.fixture(scope="module")
def config_opcua_port():
    """Dynamic port for OPC-UA server - module scoped for isolation."""
    return get_free_port()


@pytest.fixture(scope="session")
def config_host_ip():
    try:
        return socket.gethostbyname(socket.gethostname())
    except socket.gaierror:
        return "127.0.0.1"


@pytest.fixture(scope="session")
def config_eneffco():
    """Test configuration for Eneffco."""
    return {"user": "", "pw": "", "url": "", "postman_token": ""}


@pytest.fixture(scope="session")
def config_entsoe():
    """Test configuration for entso-e connection"""
    return {"path": pathlib.Path(__file__).parent / "resources/entsoe/"}


@pytest.fixture(scope="session")
def config_forecast_solar():
    """Test configuration for forecast solar."""
    return {"url": "https://api.forecast.solar"}


@pytest.fixture(scope="session")
def config_nodes_file():
    """Test configuration for reading nodes."""
    return {"file": pathlib.Path(__file__).parent / "resources/test_excel_node_list.xls", "sheet": "Sheet1"}


@pytest.fixture(scope="session")
def config_connection_manager():
    """Test configuration for connection manager."""
    return {"file": pathlib.Path(__file__).parent / "resources/connection_manager/config.json"}


# VCR configuration and fixtures below


@pytest.fixture(scope="module")
def vcr_config():
    return {
        "match_on": ["method", "uri"],
        "allow_playback_repeats": True,
    }


class _SequentialExecutor(concurrent.futures.Executor):
    """Drop-in replacement for ThreadPoolExecutor that executes all tasks synchronously
    in the calling thread.

    VCR cassette contexts are not propagated into worker threads, so multi-threaded
    execution breaks cassette recording and playback. This executor eliminates that
    problem.
    """

    def submit(self, fn, /, *args, **kwargs):
        f: concurrent.futures.Future = concurrent.futures.Future()
        try:
            f.set_result(fn(*args, **kwargs))
        except Exception as exc:
            f.set_exception(exc)
        return f

    def shutdown(self, wait: bool = True, **kwargs) -> None:  # noqa: FBT001, FBT002
        pass


@pytest.fixture(autouse=True)
def _force_sequential_http_for_vcr(request, monkeypatch):
    """Patch ThreadPoolExecutor with a synchronous executor for VCR tests.

    VCR's cassette context is not visible to worker threads, so concurrent HTTP
    requests inside a VCR test silently bypass the cassette.  Replacing the
    executor with *_SequentialExecutor* keeps every request on the calling thread
    where the cassette context lives.
    """
    if request.node.get_closest_marker("live"):
        return

    if request.node.get_closest_marker("vcr") is None:
        return

    monkeypatch.setattr(concurrent.futures, "ThreadPoolExecutor", _SequentialExecutor)


@pytest.fixture(autouse=True)
def disable_requests_cache_for_vcr(monkeypatch, request):
    # Never touch live tests
    if request.node.get_closest_marker("live"):
        return

    # Only apply to VCR tests
    if request.node.get_closest_marker("vcr") is None:
        return

    # Allow override
    if request.node.get_closest_marker("cache_enabled"):
        return

    from requests_cache import CachedSession

    original_init = CachedSession.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["disabled"] = True
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(CachedSession, "__init__", patched_init)
