import json
import pathlib
import re

from requests import Response as _Response


class Response(_Response):
    def __init__(self, json_data=None, status_code=400):
        super().__init__()
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        return self.json_data

    def text(self):
        pass


def request(self, method, url, **kwargs):  # noqa: PLR0911
    try:
        endpoint = url.split("API/v1.0/", 1)[1]
    except IndexError:
        endpoint = ""

    with pathlib.Path(__file__).parent.joinpath("eneffco_sample_data.json").open() as f:
        data = json.load(f)

    if method == "GET":
        re_readseries = re.compile(r"datapoint/(.*)/value\?from=(.*)&to=(.*)&timeInterval=(.*)&")

        if endpoint == "":
            # Empty request
            return Response(status_code=200)

        if endpoint in {"/datapoint", "/rawdatapoint"}:
            # (Raw) Datapoint IDs
            return Response(data[endpoint[1:]], 200)

        if re.match(r"datapoint\/([^\/]+)$", endpoint):
            # Datapoint Information
            _id = endpoint.split("/")[1]
            return Response(data["datapoint_info"][_id], 200)

        if re_readseries.match(endpoint):
            # Read Series
            match = re_readseries.match(endpoint)
            _id = match.groups()[0]
            timeinterval = int(match.groups()[3])

            return Response(data["series_data"][_id][::timeinterval], 200)

        if re.match(r"datapoint\/([^\/]+)/live$", endpoint):
            # Live data
            _id = endpoint.split("/")[1]
            return Response(data["live_data"][_id], 200)

        return Response(status_code=404)

    if method == "POST":
        _id = re.match(r"rawdatapoint\/([^\/]+)/value$", endpoint).groups()[0]
        status_code = 400
        if _id in [i["Id"] for i in data["rawdatapoint"]]:
            status_code = 200
        return Response(status_code=status_code)
    return None
