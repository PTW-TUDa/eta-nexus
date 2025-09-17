import os
from datetime import datetime, timedelta, timezone

from eta_nexus.connections import InfluxConnection
from eta_nexus.nodes.influx_node import InfluxNode
from eta_nexus.util.io_utils import autoload_env

autoload_env()
url = os.getenv("INFLUX_HOST")
if not url:
    raise ValueError("Set INFLUX_HOST env variable.")
node = InfluxNode(name="hum", url=url, protocol="influx", database="foo", table="home")
conn = InfluxConnection.from_node(node)
now = datetime.now(timezone.utc)
from_time = now - timedelta(hours=1)
res = conn.read_series(from_time=from_time, to_time=now)
