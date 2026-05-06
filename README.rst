ETA Nexus
#########

The ETA Nexus package provides a standardized interface for managing communication across
industrial energy and production systems. It helps handle data streams across heterogeneous
Information Technology (IT) and Operational Technology (OT) resources such as factory systems,
machines, field devices, databases, and external API services.

The package provides one unified node and connection model across multiple protocols,
including OPC UA, Modbus TCP, REST APIs, InfluxDB, SMARD, ENTSO-E, Forecast.Solar,
Wetterdienst, EnEffCo, and Emonio. It is designed for live control, operational optimization,
data recording, simulation workflows, and the integration of future communication services.

Documentation
*************

Full documentation can be found on the `Documentation Page <https://eta-nexus.readthedocs.io/en/stable/>`_.

Warning
*******

This is beta software. APIs and functionality might change without prior notice. Please fix the version you
are using in your requirements to ensure your software will not be broken by changes in ETA Nexus.

Overview
********

Core
====

``Connection``:
Base class for protocol-specific clients. Connections can be created directly or from nodes with
``Connection.from_node()`` and ``Connection.from_nodes()``.

``RESTConnection``:
Base class for REST/API connectors. It provides shared request handling, retries, cached sessions,
authentication hooks, and parsing hooks.

``ConnectionManager``:
High-level orchestration class for working with multiple systems, servers, and protocols from configuration files.
It manages initialization, activation, deactivation, closing, reading, writing, and step-based control workflows.

Nodes
=====

``Node``:
Immutable description of a single data point. A node contains the protocol, URL, authentication data,
data type, and protocol-specific addressing information.

Protocol-specific nodes:
``OpcuaNode``, ``ModbusNode``, ``InfluxNode``, ``SmardNode``, ``EntsoeNode``,
``ForecastsolarNode``, ``WetterdienstNode``, ``EneffcoNode``, and ``EmonioNode``.

Connections
===========

Status connections:
Connections that support current-value operations with ``read()``, ``write()``, and optionally ``subscribe()``.

Series connections:
Connections that support historic time-series operations with ``read_series()``, ``write_series()``,
and optionally ``subscribe_series()``.

Supported connectors include:

- OPC UA
- Modbus TCP
- InfluxDB
- SMARD
- ENTSO-E
- Forecast.Solar
- Wetterdienst
- EnEffCo
- Emonio

Servers
=======

``OpcuaServer``:
Helper for creating local OPC UA servers with simple variable access.

``ModbusServer``:
Helper for creating local Modbus TCP servers.

Subscription Handlers
=====================

``SubscriptionHandler``:
Base class for processing values received from subscriptions.

``CsvSubscriptionHandler``:
Stores subscribed values in CSV files.

``DFSubscriptionHandler``:
Stores subscribed values in memory as pandas DataFrames.

``MultiSubscriptionHandler``:
Forwards subscribed values to multiple handlers.

Time Series
===========

``df_time_slice``:
Slices time-indexed pandas DataFrames.

``df_resample``:
Resamples the time index of a DataFrame to a specified frequency.

``df_interpolate``:
Interpolates missing values in a DataFrame with a specified frequency.

``find_time_slice``:
Finds deterministic or random time slices for time-series data.

Contributing
************

Please read the `development guide <https://eta-nexus.readthedocs.io/en/stable/guide/development.html>`_
before starting development on ETA Nexus.

Citing this Project
*******************

For referencing this package in academic work, please refer to ``CITATION.cff``.
See ``AUTHORS.rst`` for a list of further contributors.
