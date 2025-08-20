import requests_cache

from eta_nexus.connections.entsoe_connection import _ConnectionConfiguration
from eta_nexus.util import dict_search


class MockResponse(requests_cache.CachedResponse):
    def __init__(self, content: str):
        super().__init__()
        self.status_code = 200
        self._content = content.encode()


def mock_get(path):
    def get(*args, params: dict[str, str], **kwargs):
        endpoint = dict_search(_ConnectionConfiguration().doc_types, params["documentType"])
        file_path = path / f"{endpoint}_sample.xml"
        with file_path.open() as file:
            return MockResponse(file.read())

    return get
