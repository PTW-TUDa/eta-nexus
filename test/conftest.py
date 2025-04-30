import asyncio
import logging
import pathlib
import platform
import random
import shutil
import socket

import pytest


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


@pytest.fixture(scope="session")
def config_modbus_port():
    if platform.system() == "Linux" or platform.system() == "Darwin":
        return 5050
    return 502


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
