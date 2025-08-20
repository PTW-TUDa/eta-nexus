from __future__ import annotations

import logging
import pathlib
import sys
from datetime import datetime
from typing import TYPE_CHECKING

from dateutil import tz

if TYPE_CHECKING:
    import io
    from typing import Any

    from eta_nexus.util.type_annotations import Path


LOG_DEBUG = 1
LOG_INFO = 2
LOG_WARNING = 3
LOG_ERROR = 4
LOG_PREFIX = "eta_nexus"
LOG_FORMATS = {
    "simple": "[%(levelname)s] %(message)s",
    "logname": "[%(levelname)s: %(name)s] %(message)s",
    "time": "[%(asctime)s - %(levelname)s - %(name)s] - %(message)s",
}


def get_logger(
    level: int = 10,
    log_format: str = "simple",
) -> logging.Logger:
    """Get eta_nexus specific logger.

    This function initializes and configures the eta_nexus's logger with the specified logging
    level and format. By default, this logger will not propagate to the root logger, ensuring that
    eta_nexus's logs remain isolated unless otherwise configured.

    Using this function is optional. The logger can be accessed and customized manually after
    retrieval.

    :param level: Logging level (lower is more verbose between 10 - Debugging and 40 - Errors).
    :param log_format: Format of the log output. One of: simple, logname, time. (default: simple).
    :return: The *eta_nexus* logger.
    """
    # Main logger
    log = logging.getLogger(LOG_PREFIX)
    log.propagate = False

    # Multiply if necessary to get the correct logging level
    if level > 0 and level < 5:
        level *= 10

    log.setLevel(level)

    # Only add handler if it does not have one already
    if not log.hasHandlers():
        log_add_streamhandler(level, log_format)

    return log


def log_add_filehandler(
    filename: Path | None = None,
    level: int = 1,
    log_format: str = "time",
) -> logging.Logger:
    """Add a file handler to the logger to save the log output.

    :param filename: File path where logger is stored.
    :param level: Logging level (higher is more verbose between 0 - no output and 4 - debug).
    :param log_format: Format of the log output. One of: simple, logname, time. (default: time).
    :return: The *FileHandler* logger.
    """
    log = logging.getLogger(LOG_PREFIX)

    if filename is None:
        log_path = pathlib.Path().cwd() / "eta_nexus_logs"
        log_path.mkdir(exist_ok=True)

        current_time = datetime.now(tz=tz.tzlocal()).strftime("%Y-%m-%d_%H-%M-%S")
        file_name = f"eta_nexus_{current_time}.log"
        log.info(f"No filename specified for filehandler. Using default filename {file_name}.")

        filename = log_path / file_name

    if log_format not in LOG_FORMATS:
        log_format = "time"
        log.warning(f"Log format {log_format} not available. Using default format 'time' for filehandler.")

    _format = LOG_FORMATS[log_format]
    _filename = pathlib.Path(filename)

    filehandler = logging.FileHandler(filename=_filename)
    filehandler.setLevel(int(level * 10))
    filehandler.setFormatter(logging.Formatter(fmt=_format))
    log.addHandler(filehandler)

    return log


def log_add_streamhandler(
    level: int = 10,
    log_format: str = "simple",
    stream: io.TextIOBase | Any = sys.stdout,
) -> logging.Logger:
    """Add a stream handler to the logger to show the log output.

    :param level: Logging level (lower is more verbose between 10 - Debugging and 40 - Errors).
    :param format: Format of the log output. One of: simple, logname, time. (default: time).
    :return: The eta_nexus logger with an attached StreamHandler
    """
    log = logging.getLogger(LOG_PREFIX)

    if log_format not in LOG_FORMATS:
        log_format = "simple"

    # Multiply if necessary to get the correct logging level
    if level > 0 and level < 5:
        level *= 10

    handler = logging.StreamHandler(stream=stream)
    handler.setLevel(level=level)
    handler.setFormatter(logging.Formatter(fmt=LOG_FORMATS[log_format]))
    log.addHandler(handler)

    return log
