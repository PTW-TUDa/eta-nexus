import json
import pathlib
import re

from requests import Response as _Response
from requests_cache import CachedResponse as _CachedResponse


class Response(_Response):
    def __init__(self, url, json_data=None, status_code=400, reason=""):
        super().__init__()
        self.url = url
        self.json_data = json_data
        self.status_code = status_code
        self.reason = "MOCK RESPONSE REASON: " + reason

    def json(self):
        return self.json_data

    def text(self):
        pass


class CachedResponse(_CachedResponse):
    def __init__(self, url, json_data=None, status_code=400, reason=""):
        super().__init__()
        self.url = url
        self.json_data = json_data
        self.status_code = status_code
        self.reason = "MOCK RESPONSE REASON: " + reason

    def json(self):
        return self.json_data

    def text(self):
        pass


def request(self, method, url: str, *args, **kwargs):
    url_path = url.split("https://api.forecast.solar", 1)[1]
    url_path = re.sub(r"^/[A-Za-z0-9]{16}/", r"/", url_path)  # Remove API key
    endpoint = re.sub(r"/\d.*", r"", url_path)  # Remove any trailing (digit) parameters

    # Cover the simple cases first
    if method == "GET":
        if endpoint in ["/help", "/check"]:
            # Empty request or check
            return CachedResponse(url, status_code=200)
        if endpoint in ["/clearsky", "/history", "/timewindows", "/weather", "/chart"]:
            raise NotImplementedError(f"Mock request of endpoint: '{endpoint}' is not implemented yet.")
    else:
        return CachedResponse(url, status_code=405)

    params = kwargs.get("params", {})
    params.pop("time", None)  # Remove time parameter

    sample_dir = pathlib.Path(__file__).parent / "forecast_solar_samples"

    # Iterate over all files in the sample directory
    for file_path in sample_dir.iterdir():
        if file_path.is_file() and file_path.suffix == ".json":
            with file_path.open() as f:
                data = json.load(f)

            _query_params = data.get("_query_params", {})
            _path = data.get("_path", "")

            # Check if the sample data matches the request
            if url_path == _path and params == _query_params:
                return CachedResponse(url, data, status_code=200)

    # If no sample data is found, thus no matching response, return 404
    return CachedResponse(url, status_code=404, reason="No sample data found for this request.")
