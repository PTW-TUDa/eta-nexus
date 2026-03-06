import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

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


def _generate_mock_filename(method: str, url: str, params: dict | None = None) -> str:
    """Generate filename matching the one used when saving."""
    parsed = urlparse(url)
    path_parts = parsed.path.strip("/").replace("/", "_")

    param_str = json.dumps(params or {}, sort_keys=True)
    param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]

    return f"{method.lower()}_{path_parts}_{param_hash}"


def request(self, method: str, url: str, params: dict | None = None, *args, **kwargs):
    """Mock request function that loads data from saved JSON file."""
    # Define your mock data directory
    mock_data_file = Path(__file__).parent / "smard_sample_data.json"

    # Generate filename based on request parameters
    filename = _generate_mock_filename(method, url, params)

    # Try to load the mock data
    if mock_data_file.exists():
        with mock_data_file.open(encoding="utf-8") as f:
            saved_data = json.load(f)

        # Look up the specific mock data by filename key
        if filename in saved_data:
            data = saved_data[filename]

            # Verify metadata matches (optional but recommended)
            metadata = data.get("metadata", {})
            if metadata.get("url") != url or metadata.get("method") != method:
                return Response(url, status_code=500, reason="Mock data metadata mismatch")

            # Return successful response with saved data
            return CachedResponse(
                url=url, json_data=data["response"], status_code=200, reason="Mock data loaded successfully"
            )
        # Mock data not found for this key
        return Response(url=url, status_code=404, reason=f"Mock data not found: {filename}")

    # Return 404 if mock data file doesn't exist
    return Response(url=url, status_code=404, reason=f"Mock data file not found: {mock_data_file}")
