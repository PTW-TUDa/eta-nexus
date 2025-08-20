from __future__ import annotations

import re
from logging import getLogger
from typing import TYPE_CHECKING
from urllib.parse import urlparse, urlunparse

if TYPE_CHECKING:
    from typing import Any
    from urllib.parse import ParseResult


log = getLogger(__name__)


def url_parse(url: str | None, scheme: str = "") -> tuple[ParseResult, str | None, str | None]:
    """Extend parsing of URL strings to find passwords and remove them from the original URL.

    :param url: URL string to be parsed.
    :return: Tuple of ParseResult object and two strings for username and password.
    """
    if url is None or url == "":
        _url = urlparse("")
    else:
        _url = urlparse(f"//{url.strip()}" if "//" not in url else url.strip(), scheme=scheme)

    # Get username and password either from the arguments or from the parsed URL string
    usr = str(_url.username) if _url.username is not None else None
    pwd = str(_url.password) if _url.password is not None else None

    # Find the "password-free" part of the netloc to prevent leaking secret info
    if usr is not None:
        match = re.search("(?<=@).+$", str(_url.netloc))
        if match:
            _url = urlparse(
                str(urlunparse((_url.scheme, match.group(), _url.path, _url.query, _url.fragment, _url.fragment)))
            )

    return _url, usr, pwd


def dict_get_any(dikt: dict[str, Any], *names: str, fail: bool = True, default: Any = None) -> Any:
    """Get any of the specified items from dictionary, if any are available.

    The function will return the first value it finds, even if there are multiple matches.

    :param dikt: Dictionary to get values from.
    :param names: Item names to look for.
    :param fail: Flag to determine, if the function should fail with a KeyError, if none of the items are found.
                 If this is False, the function will return the value specified by 'default'.
    :param default: Value to return, if none of the items are found and 'fail' is False.
    :return: Value from dictionary.
    :raise: KeyError, if none of the requested items are available and fail is True.
    """
    for name in names:
        if name in dikt:
            # Return first value found in dictionary
            return dikt[name]

    if fail is True:
        raise KeyError(
            f"Did not find one of the required keys in the configuration: {names}. Possibly Check the correct spelling"
        )
    return default


def dict_pop_any(dikt: dict[str, Any], *names: str, fail: bool = True, default: Any = None) -> Any:
    """Pop any of the specified items from dictionary, if any are available.

    The function will return
    the first value it finds, even if there are multiple matches. This function removes the found values from the
    dictionary!

    :param dikt: Dictionary to pop values from.
    :param names: Item names to look for.
    :param fail: Flag to determine, if the function should fail with a KeyError, if none of the items are found.
                 If this is False, the function will return the value specified by 'default'.
    :param default: Value to return, if none of the items are found and 'fail' is False.
    :return: Value from dictionary.
    :raise: KeyError, if none of the requested items are available and fail is True.
    """
    for name in names:
        if name in dikt:
            # Return first value found in dictionary
            return dikt.pop(name)

    if fail is True:
        raise KeyError(f"Did not find one of the required keys in the configuration: {names}")

    return default


def dict_search(dikt: dict[str, str], val: str) -> str:
    """Function to get key of _psr_types dictionary, given value.

    Raise ValueError in case of value not specified in data.

    :param val: value to search
    :param data: dictionary to search for value
    :return: key of the dictionary
    """
    for key, value in dikt.items():
        if val == value:
            return key
    raise ValueError(f"Value: {val} not specified in specified dictionary")
