import json
import pathlib

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


def request(method, url, **kwargs):
    if url == "":
        return Response(status_code=200)
    if method == "GET":
        with pathlib.Path(__file__).parent.joinpath("cumulocity_sample_data.json").open() as f:
            data = json.load(f)

        if "/measurement/measurements" in url:
            try:
                device_id = url.split("source=", 1)[1].split("&", 1)[0]
                if "valueFragmentSeries" in url:
                    fragment = url.split("&valueFragmentSeries=", 1)[1].split("&", 1)[0]
                    assert fragment == "P"
                else:
                    fragment = ""
                current_page = url.split("currentPage=", 1)[1] if "currentPage" in url else "1"
            except IndexError:
                device_id = ""

            if (current_page == "1" and device_id in {"1234", "1235"}) or current_page == "2":
                # Return data for id: 1234 and fragment: P if page is 1
                json_data = data if current_page == "1" else {"measurements": []}
                return Response(json_data, 200)

            return Response(status_code=404)
    if method == "POST":
        if "/measurement/measurements" in url:
            payload_true = {
                "source": {"id": "1234"},
                "time": "2023-12-06T08:41:26",
                "type": "power",
                "Power": {"P": {"unit": "W", "value": 1}},
            }
            if "data" not in kwargs:
                msg = "Request had no payload."
                raise Exception(msg)
            payload = json.loads(kwargs.get("data"))
            if payload != payload_true:
                msg = f"Payload was incorrect. Payload should be {payload_true}, but got {payload}."
                raise Exception(msg)
            return Response(status_code=200)

        if "/inventory/managedObjects" in url:
            assert "data" in kwargs
            assert "name" in json.loads(kwargs.get("data"))
            assert "c8y_IsDevice" in json.loads(kwargs.get("data"))
            assert json.loads(kwargs.get("data"))["name"] == "Device1"
            return Response(status_code=200)
    return None
