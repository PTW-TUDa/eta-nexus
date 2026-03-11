.. _influx_connection:

InfluxDB Connection
===================
The InfluxDB3 integration in *eta_nexus* consists of an :class:`~eta_nexus.nodes.influx_node.InfluxNode`
(that describes where a signal lives in InfluxDB) and an
:class:`~eta_nexus.connections.influx_connection.InfluxConnection`
(that knows how to read/write those signals using the official ``influxdb-client-3``).
The connector talks to **InfluxDB v3** via **SQL** and exchanges data as pandas
``DataFrame``/``Series``.

**What this module does**

- **Read latest values** per node using a generated ``SELECT`` that returns a single timestamped row.
  See :meth:`~eta_nexus.connections.influx_connection.InfluxConnection.read`.
- **Read historic series** over a half-open interval ``[from_time, to_time)`` into a time-indexed frame
  (one column per node/field).
  See :meth:`~eta_nexus.connections.influx_connection.InfluxConnection.read_series`.
- **Write current values** for one or many nodes (grouped by measurement/table).
  See :meth:`~eta_nexus.connections.influx_connection.InfluxConnection.write`.
- **Write historic series** from either a mapping ``{node: pd.Series}`` or a ``DataFrame`` whose
  columns match node fields.
  See :meth:`~eta_nexus.connections.influx_connection.InfluxConnection.write_series`.

**How nodes map to InfluxDB**

- :class:`~eta_nexus.nodes.influx_node.InfluxNode` carries:
  - ``database``: the Influx **bucket/database**.
  - ``table``: the **measurement/table**.
  - ``name``: used as the Influx **field/column** name (also available as ``node.field``).
- Nodes are **grouped by table** for efficient reads/writes; each group yields one SQL query or write call.

**Authentication & configuration**

- Pass ``token=...`` to the connection or set environment variable ``INFLUXDB3_AUTH_TOKEN``.
- The target database can be given as ``database=...``; if omitted it may be inferred from the first node
  or from ``INFLUXDB_DB`` (if set).
- The connection inherits base settings from :class:`~eta_nexus.connections.connection.Connection`
  (e.g., URL, user/password).

**Data/Time handling**

- Time series are indexed by a **datetime** index named ``time`` (UTC recommended).
  The connector will error if the index is not datetime-like.
- Reads return frames with **requested columns ordered** as the input node order.
- For historic reads the interval is **half-open** ``[from_time, to_time)``; writes preserve exact timestamps.

**Notes & limitations**

- This connector targets **InfluxDB v3 + SQL**; it does not use Flux.
- When writing a ``DataFrame``, **all columns must correspond** to known node fields; unknown columns raise
  a ``ValueError``.
- Some server-side resampling parameters (e.g., ``interval``) are accepted for API compatibility and may be
  ignored by the backend.

See the API sections below for the full class/method reference and the example for a minimal end-to-end read.


Influx Node
-----------

.. autoclass:: eta_nexus.nodes::InfluxNode
    :members:
    :inherited-members:
    :noindex:

Influx Connection
-----------------

.. autoclass:: eta_nexus.connections::InfluxConnection
    :members:
    :inherited-members:
    :noindex:

Example Usage
-------------

.. literalinclude:: ../../examples/connections/read_influx.py
   :language: python
   :linenos:
