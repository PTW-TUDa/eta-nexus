"""VCR scrubbing and matching utilities for Forecast.Solar tests.

forecast.solar embeds the API key as a 16-character alphanumeric path segment:
  https://api.forecast.solar/<API_KEY>/estimate/...

All functions below normalise URLs by stripping that segment so cassettes
contain no real credentials and replay works regardless of which key is used.
"""

import re


def scrub_uri(uri: str) -> str:
    """Remove the 16-char API key path segment from a forecast.solar URI."""
    return re.sub(r"(api\.forecast\.solar)/[A-Za-z0-9]{16}/", r"\1/", uri)


def _scrub_request(request):
    """Rewrite URI to strip API key before the interaction is written to cassette."""
    request.uri = scrub_uri(request.uri)
    return request


def _scrub_response(response):
    """Strip API key occurrences from the response body and remove rate-limit headers."""
    response["body"]["string"] = re.sub(
        r"[A-Za-z0-9]{16}", "REDACTED", response["body"]["string"].decode("utf-8")
    ).encode("utf-8")
    response["headers"].pop("X-Ratelimit-Zone", None)
    return response


def custom_matcher(r1, r2) -> bool:
    """VCR matcher that strips API key before comparing URIs."""
    return scrub_uri(r1.uri) == scrub_uri(r2.uri)
