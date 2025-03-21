from datetime import datetime, timedelta

import pandas as pd

from eta_connect.connectors.cumulocity import CumulocityConnection
from eta_connect.connectors.node import NodeCumulocity

# Params for example Cumulocity-Connection
URL = "eta-iot-cumulocity.ptw.maschinenbau.tu-darmstadt.de"
DEVICE_ID = "2496822328"
MEASUREMENT = "Example-Measurement"
FRAGMENT = "Power"
USER = ""  # enter username here
PASSWORD = ""  # enter your password here
TENANT = "edge"

cumu_node = NodeCumulocity(
    "Cumulocity-Test-Node",
    URL,
    "cumulocity",
    device_id=DEVICE_ID,
    measurement=MEASUREMENT,
    fragment=FRAGMENT,
)

cumu_node2 = NodeCumulocity(
    "Cumulocity-Test-Node2",
    URL,
    "cumulocity",
    device_id=DEVICE_ID,
    measurement=MEASUREMENT,
    fragment=FRAGMENT,
)

### Create Connection ###
# 1. Example: Create connection via connection class
conn = CumulocityConnection(url=URL, usr=USER, pwd=PASSWORD, tenant=TENANT)

# 2. Example: Create connection by Node
conn2: CumulocityConnection = CumulocityConnection.from_node(
    [cumu_node, cumu_node2], usr=USER, pwd=PASSWORD, tenant=TENANT
)  # type: ignore
# this way the nodes are directly saved in conn.selected_nodes

### Write Data ###
# Create Example data
t = datetime.now()
index = [t, t + timedelta(minutes=1), t + timedelta(minutes=2)]
data = pd.DataFrame(data=[[1], [2], [3]], columns=["P"], index=index)

# Write data
# to write data you need to provide the additional parameters measurement_type and unit and pass the data as pd.Series
# you can either provide the upload nodes manually
conn.write(values=data["P"], measurement_type="Power", unit="W", nodes={cumu_node})

### Read Data ###
# to read data you need to provide the nodes to read from and a timespan
# again you can either provide the download nodes manually
print(conn.read_series(from_time=t, to_time=t + timedelta(minutes=5), nodes={cumu_node}))  # noqa

### Create Device ###
# to create a device, additionally to your login information, you need to provide a device name
DEVICE_NAME = ""
# CumulocityConnection.create_device(url=URL,
# username=USER, password=PASSWORD, tenant=TENANT, device_name=DEVICE_NAME)
