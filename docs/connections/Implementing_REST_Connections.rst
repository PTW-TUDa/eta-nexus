Guide: Building REST API Connections in eta-nexus
=================================================

This guide walks you through the complete process of creating a new
REST-based connection for the eta-nexus framework, from initial API
exploration to full integration.

Table of Contents
-----------------

1. Overview
2. Phase 1: API Analysis
3. Phase 2: Node Design
4. Phase 3: Connection Implementation
5. Phase 4: Testing
6. Phase 5: Documentation
7. Quick Reference

--------------

Overview
--------

Creating a REST connection involves five phases:

1. **API Analysis** - Understanding the API structure and behavior
2. **Node Design** - Defining data point representation
3. **Connection Implementation** - Building the connection class
4. **Testing** - Ensuring reliability and correctness
5. **Documentation** - Enabling others to use your connection

**Architecture**: REST connections inherit from
```RESTConnection[YourNode]`` `__
and implement capability protocols: - ``Readable`` - Read current values
- ``SeriesReadable`` - Read time series - ``Writable`` - Write values -
``Subscribable`` - Subscribe to updates

**Reference Implementations**: - Simple REST API:
``ForecastsolarConnection`` - Complex REST API with write:
``EneffcoConnection``

--------------

Phase 1: API Analysis
---------------------

Step 1.1: Manual Exploration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Start by making direct HTTP requests to understand the API. Use Python’s
``requests`` library:

.. code:: python

   import requests
   from datetime import datetime, timezone

   # Basic GET request
   response = requests.get(
       "https://api.example.com/v1/data", headers={"Accept": "application/json"}, params={"start": "2024-01-01T00:00:00Z"}
   )

   print(f"Status: {response.status_code}")
   print(f"Headers: {response.headers}")
   print(f"JSON: {response.json()}")

**Key questions to answer:**

Authentication
^^^^^^^^^^^^^^

-  [ ] What authentication method? (Basic Auth, Bearer Token, API Key,
   OAuth)
-  [ ] Where is auth provided? (Headers, Query params, Request body)
-  [ ] Are credentials in environment variables?

.. code:: python

   # Test different auth methods
   # Basic Auth
   response = requests.get(url, auth=("username", "password"))

   # Bearer Token
   response = requests.get(url, headers={"Authorization": "Bearer YOUR_TOKEN"})

   # API Key in query
   response = requests.get(url, params={"api_key": "YOUR_KEY"})

Endpoints & URL Structure
^^^^^^^^^^^^^^^^^^^^^^^^^

-  [ ] What endpoints exist? (``/data``, ``/history``, ``/stations``,
   etc.)
-  [ ] How are resources identified? (Path params, query params)
-  [ ] What’s the base URL pattern?

.. code:: python

   # Document URL patterns
   base_url = "https://api.example.com"
   # Pattern: {base_url}/{version}/{resource}/{identifier}?{params}
   # Example: https://api.example.com/v1/stations/12345/data?from=2024-01-01

Request Parameters
^^^^^^^^^^^^^^^^^^

-  [ ] Required parameters (endpoint, time range, identifiers)
-  [ ] Optional parameters (format, units, aggregation)
-  [ ] Parameter formats (ISO datetime, Unix timestamp, etc.)

.. code:: python

   # Test parameter variations
   params = {
       "station_id": "12345",
       "start": "2024-01-01T00:00:00Z",  # ISO format?
       "end": 1704153600,  # Unix timestamp?
       "interval": 3600,  # Seconds? Minutes?
       "format": "json",  # Response format
   }

Response Structure
^^^^^^^^^^^^^^^^^^

-  [ ] What format? (JSON, XML, CSV)
-  [ ] How are timestamps represented?
-  [ ] How are values structured?
-  [ ] How are errors indicated?

.. code:: python

   # Analyze successful response
   response = requests.get(url, params=params)
   data = response.json()

   # Document structure:
   # {
   #   "metadata": {"station": "12345", "units": "celsius"},
   #   "data": [
   #     {"timestamp": "2024-01-01T00:00:00Z", "value": 20.5},
   #     {"timestamp": "2024-01-01T01:00:00Z", "value": 20.3}
   #   ]
   # }

   # Test error responses
   bad_response = requests.get(url, params={"invalid": "param"})
   print(f"Error: {bad_response.status_code}, {bad_response.text}")

Rate Limiting & Caching
^^^^^^^^^^^^^^^^^^^^^^^

-  [ ] Are there rate limits? (requests/minute, daily quotas)
-  [ ] How stable is the data? (Cache duration)
-  [ ] Are there cache headers? (``Cache-Control``, ``ETag``)

.. code:: python

   print(response.headers.get("X-RateLimit-Remaining"))
   print(response.headers.get("Cache-Control"))

Step 1.2: Document Your Findings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create a summary document:

\```markdown # Your API Analysis

.. _authentication-1:

Authentication
--------------

-  Method: Bearer Token
-  Location: ``Authorization: Bearer {token}``
-  Environment Variable: ``YOUR_API_TOKEN``

Base URL
--------

-  Production: ``https://api.example.com/v1``
-  Pattern: ``{base}/{endpoint}/{resource_id}``

Endpoints
---------

GET /stations/{id}/data
~~~~~~~~~~~~~~~~~~~~~~~

-  Purpose: Retrieve time series data
-  Required params: ``start``, ``end``
-  Optional params: ``interval`` (default: 3600)
-  Response: JSON with timestamps (ISO 8601) and float values

Example Request
---------------

.. code:: bash

   curl -X GET "https://api.example.com/v1/stations/12345/data?start=2024-01-01T00:00:00Z&end=2024-01-02T00:00:00Z" \
   -H "Authorization: Bearer abc123..."

Example Response
----------------

.. code:: json

   {
     "station_id": "12345",
     "data": [
       {"time": "2024-01-01T00:00:00Z", "value": 20.5},
       {"time": "2024-01-01T01:00:00Z", "value": 20.3}
     ]
   }

Rate Limits
-----------

-  1000 requests/hour
-  Cache responses for 15 minutes

Timezone Handling
-----------------

-  API always returns UTC
-  Convert to local timezone in connection

--------------

Phase 2: Node Design
--------------------

Nodes represent individual data points. Design your node to capture all
information needed to uniquely identify and access a data point.

Step 2.1: Identify Node Attributes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Based on your API analysis, determine what attributes each node needs:

**From API Requirements:** - Endpoint identification (station ID,
parameter name, etc.) - Location data (if applicable) - Configuration
parameters - API-specific settings

**Example Mapping:**

==================== ============================ ========= =================
API Concept          Node Attribute               Type      Example
==================== ============================ ========= =================
Station ID           ``station_id``               ``str``   ``"12345"``
Parameter            ``parameter``                ``str``   ``"temperature"``
Units                ``units``                    ``str``   ``"celsius"``
Latitude/Longitude   ``latitude``, ``longitude``  ``float`` ``52.52, 13.40``
==================== ============================ ========= =================

Step 2.2: Implement Node Class
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create your node in ```eta_nexus/nodes/`` `__:

.. code:: python

   from __future__ import annotations

   from typing import TYPE_CHECKING

   from attrs import field, validators

   from eta_nexus.nodes import Node

   if TYPE_CHECKING:
       from typing import Any


   class YourApiNode(Node, protocol="your_api"):
       """Node for Your API connection.

       :param station_id: Station identifier from the API
       :param parameter: Parameter to measure (e.g., 'temperature', 'humidity')
       :param units: Measurement units (optional, defaults from API)
       """

       # Required: Uniquely identify the data point
       station_id: str = field(kw_only=True, converter=str)
       parameter: str = field(
           kw_only=True, converter=str, validator=validators.in_(["temperature", "humidity", "pressure"])
       )

       # Optional: Additional configuration
       units: str | None = field(default=None, kw_only=True, converter=lambda x: str(x) if x else None)

       def __attrs_post_init__(self) -> None:
           """Validate and process node attributes."""
           super().__attrs_post_init__()

           # Add custom validation
           if self.station_id.startswith("TEST_") and self.url != "https://test.example.com":
               raise ValueError("Test stations must use test URL")

       @classmethod
       def _from_dict(cls, dikt: dict[str, Any]) -> YourApiNode:
           """Create node from dictionary (for config files).

           :param dikt: Dictionary with node configuration
           :return: YourApiNode instance
           """
           # Read common parameters (name, url, usr, pwd, interval)
           name, pwd, url, usr, interval = cls._read_dict_info(dikt)

           # Extract API-specific parameters
           try:
               station_id = cls._try_dict_get_any(dikt, "station_id", "station", "id")
               parameter = cls._try_dict_get_any(dikt, "parameter", "param")
           except KeyError as e:
               raise KeyError(f"Required parameter missing for node {name}: {e}") from e

           # Optional parameters
           units = dikt.get("units")

           try:
               return cls(
                   name=name,
                   url=url,
                   protocol="your_api",
                   usr=usr,
                   pwd=pwd,
                   interval=interval,
                   station_id=station_id,
                   parameter=parameter,
                   units=units,
               )
           except (TypeError, AttributeError) as e:
               raise TypeError(f"Could not create node {name}: {e}") from e

**Key Design Decisions:**

1. **Required vs Optional**: Mark required attributes with validators
2. **Type Conversion**: Use ``converter`` to ensure correct types
3. **Validation**: Implement ``__attrs_post_init__`` for complex
   validation
4. **Config Loading**: Implement ``_from_dict`` for JSON/Excel
   configuration support

See ``ForecastsolarNode`` for a complex example with URL building, and
``EneffcoNode`` for a simple example.

--------------

Phase 3: Connection Implementation
----------------------------------

Step 3.1: Create Connection Class Skeleton
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create ``eta_nexus/connections/your_api_connection.py``:

.. code:: python

   from __future__ import annotations

   from datetime import datetime, timedelta
   from logging import getLogger
   from typing import TYPE_CHECKING, cast

   import pandas as pd
   from requests_cache import CachedSession

   from eta_nexus.connections.connection import (
       Readable,
       RESTConnection,
       SeriesReadable,
   )
   from eta_nexus.nodes import YourApiNode

   if TYPE_CHECKING:
       from typing import Any

       from pandas._typing import ArrayLike
       from eta_nexus.util.type_annotations import Nodes, TimeStep


   class YourApiConnection(
       RESTConnection[YourApiNode],
       Readable[YourApiNode],
       SeriesReadable[YourApiNode],
       protocol="your_api",
   ):
       """Connection to Your API service.

       Environment Variables:
           YOUR_API_TOKEN: Authentication token (required)

       :param url: Base URL (default: https://api.example.com)
       :param usr: Username (if using Basic Auth)
       :param pwd: Password (if using Basic Auth)
       :param nodes: Nodes to select in connection
       """

       API_PATH: str = "/v1"

       logger = getLogger(__name__)

       def __init__(
           self,
           url: str = "https://api.example.com",
           usr: str | None = None,
           pwd: str | None = None,
           *,
           nodes: Nodes[YourApiNode] | None = None,
       ) -> None:
           url = url.rstrip("/") + self.API_PATH
           super().__init__(url, usr, pwd, nodes=nodes)

           # Validate authentication
           if self._api_token is None:
               raise ValueError(
                   "YOUR_API_TOKEN environment variable is not set. " "Set it with: export YOUR_API_TOKEN='your_token'"
               )

Step 3.2: Implement Session & Authentication
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Based on your Phase 1 analysis, configure the session:

.. code:: python

   def _initialize_session(self) -> CachedSession:
       """Initialize the cached request session."""
       self._cached_session = CachedSession(
           cache_name="eta_nexus/connections/requests_cache/your_api_cache",
           expire_after=timedelta(minutes=15),  # From your rate limit analysis
           allowable_codes=(200, 400, 401, 403),
           use_cache_dir=True,
       )

       # Set authentication
       self._cached_session.auth = self.authentication

       # Set headers
       self._cached_session.headers.update(
           {
               "Content-Type": "application/json",
               "Accept": "application/json",
           }
       )

       return self._cached_session


   @property
   def authentication(self) -> requests.auth.HTTPBasicAuth | None:
       """Return authentication for the API."""
       # Pattern 1: Bearer Token (most common)
       # Handled in _initialize_session via headers
       # if self._api_token:
       #     self._cached_session.headers["Authorization"] = f"Bearer {self._api_token}"

       # Pattern 2: Basic Auth
       if self.usr and self.pwd:
           return requests.auth.HTTPBasicAuth(self.usr, self.pwd)

       # Pattern 3: No auth (public API)
       return None

**Authentication Patterns by API Type:**

================ =========================================
================
Pattern          Implementation                            Example
================ =========================================
================
Bearer Token     Header: ``Authorization: Bearer {token}`` Most modern APIs
Basic Auth       ``HTTPBasicAuth(user, pwd)``              Older APIs
API Key (Header) Header: ``X-API-Key: {key}``              Simple APIs
API Key (Query)  URL param: ``?api_key={key}``             Public APIs
================ =========================================
================

Step 3.3: Implement Core Methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Factory Method
^^^^^^^^^^^^^^

.. code:: python

   @classmethod
   def _from_node(
       cls,
       node: YourApiNode,
       usr: str | None = None,
       pwd: str | None = None,
       **kwargs: Any,
   ) -> YourApiConnection:
       """Initialize connection from a node.

       :param node: Node to initialize from
       :param usr: Override username
       :param pwd: Override password
       :return: YourApiConnection instance
       """
       return super()._from_node(node, usr=usr, pwd=pwd, **kwargs)

Response Parser
^^^^^^^^^^^^^^^

This is the **critical method** that transforms API responses into
pandas-compatible data:

.. code:: python

   def _parse_response(self, json_data: dict[Any, Any]) -> tuple[pd.DatetimeIndex, ArrayLike]:
       """Parse JSON response into (timestamps, values).

       Based on your Phase 1 analysis, extract timestamps and values
       from the API's JSON structure.

       :param json_data: Parsed JSON from API
       :return: (DatetimeIndex, values) tuple
       """
       # Example 1: Simple list structure
       # {"data": [{"time": "...", "value": 123}, ...]}
       timestamps = pd.to_datetime(
           [item["time"] for item in json_data["data"]],
           utc=True,  # ALWAYS parse as UTC first
       )
       values = [item["value"] for item in json_data["data"]]

       # Example 2: Nested structure
       # {"station": "123", "measurements": {"timestamps": [...], "values": [...]}}
       # timestamps = pd.to_datetime(json_data["measurements"]["timestamps"], utc=True)
       # values = json_data["measurements"]["values"]

       # Example 3: Key-value pairs
       # {"2024-01-01T00:00:00Z": 123, "2024-01-01T01:00:00Z": 124}
       # timestamps = pd.to_datetime(list(json_data.keys()), utc=True)
       # values = list(json_data.values())

       return timestamps, values

**Important**: The return type can be: - **List/tuple**:
``[1.0, 2.0, 3.0]`` - automatically aligned - **Numpy array**:
``np.array([1.0, 2.0, 3.0])`` - automatically aligned - **Generator**:
``(x for x in data)`` - memory efficient - **Pandas Series**:
``pd.Series([1.0, 2.0, 3.0], index=timestamps)`` - **index MUST match
timestamps**

Node Reader
^^^^^^^^^^^

.. code:: python

   def read_node(self, node: YourApiNode, **kwargs: Any) -> pd.DataFrame:
       """Read data for a single node.

       Constructs the API request URL based on node attributes and
       time range from kwargs.

       :param node: Node to read from
       :param kwargs: Contains from_time, to_time, interval from read_series
       :return: DataFrame with node data
       """
       # Extract time range (provided by read_series)
       from_time = cast("datetime", kwargs.get("from_time"))
       to_time = cast("datetime", kwargs.get("to_time"))
       interval = cast("timedelta", kwargs.get("interval"))

       # Build API request URL
       request_url = (
           f"{self.url}/stations/{node.station_id}/data?"
           f"start={self._format_datetime(from_time)}&"
           f"end={self._format_datetime(to_time)}&"
           f"interval={int(interval.total_seconds())}"
       )

       # Build query parameters
       params = {"parameter": node.parameter}
       if node.units:
           params["units"] = node.units

       # Delegate to base class (handles request + parsing + DataFrame creation)
       return super()._read_node(node, request_url, params=params)


   def _format_datetime(self, dt: datetime) -> str:
       """Format datetime for API (from Phase 1 analysis).

       :param dt: Datetime to format
       :return: API-compatible string
       """
       # ISO 8601 format
       return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

       # Alternative: URL-encoded
       # return dt.isoformat(sep="T", timespec="seconds").replace(":", "%3A")

Step 3.4: Implement Optional Methods
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Current Value Reading (Readable Protocol)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: python

   def read(self, nodes: YourApiNode | Nodes[YourApiNode] | None = None) -> pd.DataFrame:
       """Read current values.

       :param nodes: Nodes to read from
       :return: DataFrame with current values
       """
       nodes = self._validate_nodes(nodes)

       # Option 1: Use read_series with small window
       now = datetime.now(tz=self._local_tz)
       return self.read_series(
           from_time=now - timedelta(seconds=1),
           to_time=now,
           nodes=nodes,
           interval=1,
       )

       # Option 2: Use dedicated /latest endpoint (if available)
       # results = []
       # for node in nodes:
       #     url = f"{self.url}/stations/{node.station_id}/latest"
       #     response = self._raw_request("GET", url)
       #     # ... parse and append to results
       # return pd.concat(results, axis=1)

Utility Methods
^^^^^^^^^^^^^^^

.. code:: python

   def _validate_station(self, station_id: str) -> bool:
       """Check if station exists.

       :param station_id: Station ID to validate
       :return: True if valid
       """
       response = self._raw_request("GET", f"{self.url}/stations/{station_id}")
       return response is not None and response.status_code == 200

Step 3.5: Register Connection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Add to **init**.py:

.. code:: python

   from eta_nexus.connections.your_api_connection import YourApiConnection as YourApiConnection

--------------

Phase 4: Testing
----------------

Step 4.1: Create Test File
~~~~~~~~~~~~~~~~~~~~~~~~~~

Create ``test/test_connections/test_your_api.py``:

.. code:: python

   from datetime import datetime, timedelta, timezone

   import pandas as pd
   import pytest

   from eta_nexus.connections import YourApiConnection
   from eta_nexus.nodes import YourApiNode


   @pytest.fixture
   def sample_node():
       """Create a test node."""
       return YourApiNode(
           name="test_station",
           url="https://api.example.com",
           protocol="your_api",
           station_id="12345",
           parameter="temperature",
       )


   @pytest.fixture
   def connection(sample_node):
       """Create a test connection."""
       return YourApiConnection.from_node(sample_node)


   def test_initialization(connection):
       """Test connection creation."""
       assert connection.url == "https://api.example.com/v1"
       assert len(connection.selected_nodes) == 1


   def test_node_creation():
       """Test node attributes."""
       node = YourApiNode(
           name="temp_sensor",
           url="https://api.example.com",
           protocol="your_api",
           station_id="12345",
           parameter="temperature",
           units="celsius",
       )
       assert node.station_id == "12345"
       assert node.parameter == "temperature"
       assert node.units == "celsius"


   def test_read_series(connection, sample_node):
       """Test reading time series data."""
       from_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
       to_time = datetime(2024, 1, 2, tzinfo=timezone.utc)

       result = connection.read_series(
           from_time=from_time,
           to_time=to_time,
           nodes=sample_node,
           interval=timedelta(hours=1),
       )

       assert isinstance(result, pd.DataFrame)
       assert sample_node.name in result.columns
       assert result.index.name == "Time (with timezone)"
       assert len(result) > 0


   def test_authentication_required(monkeypatch):
       """Test that missing token raises error."""
       monkeypatch.delenv("YOUR_API_TOKEN", raising=False)

       node = YourApiNode(
           name="test",
           url="https://api.example.com",
           protocol="your_api",
           station_id="12345",
           parameter="temperature",
       )

       with pytest.raises(ValueError, match="YOUR_API_TOKEN"):
           YourApiConnection.from_node(node)

Step 4.2: Mock API Responses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create ``test/utilities/requests/your_api_request.py``:

.. code:: python

   import re
   from typing import Any

   from test.utilities.requests.response import Response


   class MockYourApiRequests:
       """Mock HTTP requests for Your API."""

       def __init__(self, sample_data: dict[str, Any]) -> None:
           self.data = sample_data

       def request(self, method: str, url: str, **kwargs: Any) -> Response:
           """Mock request handler."""
           if method == "GET":
               # Match /stations/{id}/data endpoint
               match = re.search(r"/stations/(\w+)/data", url)
               if match:
                   station_id = match.group(1)
                   if station_id in self.data:
                       return Response(self.data[station_id], 200)
                   return Response({"error": "Station not found"}, 404)

           return Response({"error": "Invalid request"}, 400)


   # Usage in test
   @pytest.fixture
   def mock_requests(monkeypatch):
       """Mock API requests."""
       sample_data = {
           "12345": {
               "data": [
                   {"time": "2024-01-01T00:00:00Z", "value": 20.5},
                   {"time": "2024-01-01T01:00:00Z", "value": 20.3},
               ]
           }
       }

       mock = MockYourApiRequests(sample_data)
       monkeypatch.setattr("requests.Session.request", mock.request)

Step 4.3: Run Tests
~~~~~~~~~~~~~~~~~~~

.. code:: bash

   # Run all tests
   pytest test/test_connections/test_your_api.py

   # Run with coverage
   pytest --cov=eta_nexus.connections.your_api_connection test/test_connections/test_your_api.py

   # Run specific test
   pytest test/test_connections/test_your_api.py::test_read_series -v

--------------

Phase 5: Documentation
----------------------

Step 5.1: Create Documentation File
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create ``docs/connections/your_api.rst``:

.. code:: rst

   .. _your_api_connection:

   Your API Connection
   ===================

   This module provides a connection to the Your API service for retrieving
   time series data from weather stations.

   **Features:**

   - Read current values via :meth:`~eta_nexus.connections.your_api_connection.YourApiConnection.read`
   - Read time series via :meth:`~eta_nexus.connections.your_api_connection.YourApiConnection.read_series`
   - Automatic request caching (15 minutes)
   - Timezone-aware datetime handling

   **Authentication:**

   Set the ``YOUR_API_TOKEN`` environment variable:

   .. code-block:: bash

       export YOUR_API_TOKEN="your_token_here"

   YourApiConnection
   -----------------

   .. autoclass:: eta_nexus.connections::YourApiConnection
       :members:
       :inherited-members:
       :noindex:

   YourApiNode
   -----------

   .. autoclass:: eta_nexus.nodes::YourApiNode
       :members:
       :inherited-members:
       :exclude-members: protocol, as_dict, as_tuple, evolve
       :noindex:

   Example Usage
   -------------

   Basic example reading time series data:

   .. code-block:: python

       from datetime import datetime, timezone, timedelta
       from eta_nexus.connections import YourApiConnection
       from eta_nexus.nodes import YourApiNode

       # Create node
       node = YourApiNode(
           name="temperature_sensor",
           url="https://api.example.com",
           protocol="your_api",
           station_id="12345",
           parameter="temperature",
           units="celsius",
       )

       # Create connection
       conn = YourApiConnection.from_node(node)

       # Read time series
       from_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
       to_time = datetime(2024, 1, 2, tzinfo=timezone.utc)

       data = conn.read_series(
           from_time=from_time,
           to_time=to_time,
           nodes=node,
           interval=timedelta(hours=1),
       )

       print(data)

   Multiple nodes example:

   .. code-block:: python

       # Create multiple nodes
       temp_node = YourApiNode(
           name="temperature",
           url="https://api.example.com",
           protocol="your_api",
           station_id="12345",
           parameter="temperature",
       )

       humidity_node = YourApiNode(
           name="humidity",
           url="https://api.example.com",
           protocol="your_api",
           station_id="12345",
           parameter="humidity",
       )

       # Read from multiple nodes
       conn = YourApiConnection.from_node([temp_node, humidity_node])
       data = conn.read_series(from_time, to_time, interval=3600)

       # Result has columns: ['temperature', 'humidity']

Step 5.2: Add to Documentation Index
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Update introduction.rst or index.rst:

.. code:: rst

   .. toctree::
       :maxdepth: 1
       :caption: Connections

       /connections/introduction
       /connections/your_api
       ...

Step 5.3: Update README
~~~~~~~~~~~~~~~~~~~~~~~

Add your connection to the table in README.rst:

.. code:: rst

   .. list-table:: Connection Types
      :widths: 30 20 20
      :header-rows: 1

      * - Connection
        - StatusConnectionType
        - SeriesConnectionType
      ...
      * - Your API (``YourApi``)
        - ✓
        - ✓

--------------

Quick Reference
---------------

Minimal Working Example
~~~~~~~~~~~~~~~~~~~~~~~

.. code:: python

   # Node (nodes/your_api_node.py)
   class YourApiNode(Node, protocol="your_api"):
       station_id: str = field(kw_only=True, converter=str)

       @classmethod
       def _from_dict(cls, dikt: dict[str, Any]) -> YourApiNode:
           name, pwd, url, usr, interval = cls._read_dict_info(dikt)
           station_id = cls._try_dict_get_any(dikt, "station_id")
           return cls(name, url, "your_api", usr=usr, pwd=pwd, station_id=station_id)


   # Connection (connections/your_api_connection.py)
   class YourApiConnection(
       RESTConnection[YourApiNode],
       SeriesReadable[YourApiNode],
       protocol="your_api",
   ):
       def _initialize_session(self) -> CachedSession:
           self._cached_session = CachedSession(cache_name="your_api_cache")
           return self._cached_session

       @classmethod
       def _from_node(cls, node: YourApiNode, **kwargs: Any) -> YourApiConnection:
           return super()._from_node(node, **kwargs)

       def _parse_response(self, json_data: dict[Any, Any]) -> tuple[pd.DatetimeIndex, ArrayLike]:
           timestamps = pd.to_datetime([d["time"] for d in json_data["data"]], utc=True)
           values = [d["value"] for d in json_data["data"]]
           return timestamps, values

       def read_node(self, node: YourApiNode, **kwargs: Any) -> pd.DataFrame:
           from_time = cast("datetime", kwargs.get("from_time"))
           to_time = cast("datetime", kwargs.get("to_time"))
           url = f"{self.url}/stations/{node.station_id}/data?start={from_time}&end={to_time}"
           return super()._read_node(node, url)

Common Patterns
~~~~~~~~~~~~~~~

**Authentication:**

.. code:: python

   # Bearer Token
   def _initialize_session(self):
       session = CachedSession(...)
       session.headers["Authorization"] = f"Bearer {self._api_token}"
       return session


   # Basic Auth
   @property
   def authentication(self):
       return requests.auth.HTTPBasicAuth(self.usr, self.pwd)


   # API Key in URL
   def read_node(self, node, **kwargs):
       params = {"api_key": self._api_token}
       return super()._read_node(node, url, params=params)

**Error Handling:**

.. code:: python

   def _parse_response(self, json_data):
       try:
           timestamps = pd.to_datetime(json_data["times"], utc=True)
           values = json_data["values"]
       except (KeyError, ValueError, TypeError) as e:
           self.logger.error(f"Failed to parse response: {e}")
           return pd.DatetimeIndex([]), []
       return timestamps, values

**Timezone Conversion:**

.. code:: python

   # API returns UTC, convert to local
   timestamps = pd.to_datetime(data["times"], utc=True)
   # Conversion to local happens automatically in _read_node:
   # index=timestamps.tz_convert(self._local_tz)

Checklist
~~~~~~~~~

**Phase 1: API Analysis** - [ ] Tested API with ``requests.get()`` - [ ]
Documented authentication method - [ ] Documented URL structure and
endpoints - [ ] Documented request parameters - [ ] Documented response
format - [ ] Checked rate limits and caching

**Phase 2: Node Design** - [ ] Created node class with required
attributes - [ ] Implemented ``__attrs_post_init__`` validation - [ ]
Implemented ``_from_dict`` for config loading - [ ] Added type
converters and validators

**Phase 3: Connection Implementation** - [ ] Created connection class
inheriting from ``RESTConnection`` - [ ] Implemented
``_initialize_session`` - [ ] Implemented ``authentication`` property -
[ ] Implemented ``_from_node`` classmethod - [ ] Implemented
``_parse_response`` - [ ] Implemented ``read_node`` - [ ] Implemented
optional ``read`` method - [ ] Added utility methods - [ ] Registered in
**init**.py

**Phase 4: Testing** - [ ] Created test file - [ ] Wrote unit tests for
node creation - [ ] Wrote unit tests for connection initialization - [ ]
Wrote unit tests for data reading - [ ] Created mock responses - [ ] All
tests passing

**Phase 5: Documentation** - [ ] Created RST documentation file - [ ]
Added API reference (autoclass) - [ ] Added usage examples - [ ] Updated
documentation index - [ ] Updated README

Troubleshooting
~~~~~~~~~~~~~~~

+----------------------------+-----------------------------------------+
| Issue                      | Solution                                |
+============================+=========================================+
| NaN values in DataFrame    | Ensure Series index matches timestamps  |
|                            | in ``_parse_response``                  |
+----------------------------+-----------------------------------------+
| Timezone errors            | Always parse timestamps with            |
|                            | ``utc=True``                            |
+----------------------------+-----------------------------------------+
| Authentication failures    | Check environment variables, verify     |
|                            | token format                            |
+----------------------------+-----------------------------------------+
| Empty DataFrame            | Add logging to ``read_node``, check URL |
|                            | construction                            |
+----------------------------+-----------------------------------------+
| Rate limiting              | Implement retry logic with              |
|                            | ``HTTPAdapter``                         |
+----------------------------+-----------------------------------------+

References
~~~~~~~~~~

-  **Architecture**: ``RESTConnection``
-  **Simple Example**: ``ForecastsolarConnection``
-  **Complex Example**: ``EneffcoConnection``
-  **Node Base**: ``Node``
-  **Testing Utilities**: requests
-  **Documentation**: introduction.rst
