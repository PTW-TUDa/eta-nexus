ETA Connect
#############

*ETA Connect* is a Python package designed to manage and facilitate inbound as well as outbound connections to various endpoints, including PLC controllers, field devices, and API services. The package aims to provide standardized connectivity through one unified notation across multiple communication protocols, currently supporting OPC UA, Modbus TCP, and REST.

If you want to record timeseries continuously, you can also use the `Datarecorder Application <https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-datarecorder>`_ which uses the *eta_connect* package. Currently, only StatusConnectionType-Connections are supported by the Datarecorder.

Docs
*******
`Full documentation can be found here: eta-connect.readthedocs.io (TODO: Make this a link as soon as first docs version is released.)

.. warning::

   This is beta software. APIs and functionality may change significantly in major releases, and old major releases do not receive bug fixes.

Currently Available Connection Protocols
=========================================

.. image:: _static/eta_connect.svg
   :alt: See the docs for ETA Connect's Class structure


There are two interfaces for connections: ``StatusConnectionType`` and ``SeriesConnectionType``.
While ``StatusConnectionType`` implements ``read()`` and ``write()``, to handle the current value of the endpoint,
``SeriesConnectionType`` implements ``read_series()``, yielding historic data without an ability to write to endpoints.
``Connection`` s can implement both interfaces.

.. list-table:: Connection Types
   :widths: 30 20 20
   :header-rows: 1

   * - Connection
     - StatusConnectionType
     - SeriesConnectionType
   * - Emonio (``Emonio``)
     - ✓
     -
   * - Modbus TCP (``Modbus``)
     - ✓
     -
   * - OPC UA (``Opcua``)
     - ✓
     -
   * - ENTSO-E (``Entsoe``)
     -
     - ✓
   * - ForecastSolar (``Forecastsolar``)
     -
     - ✓
   * - Wetterdienst (``Wetterdienst``)
     -
     - ✓
   * - EnEffco (``Eneffco``)
     - ✓
     - ✓
   * - etaONE (``Etaone``)
     - ✓
     - ✓


Contributing
=============

Please read the :doc:`development guide <guide/development>` before starting development on *eta_connect*

Citing this Project / Authors
================================

See :doc:`AUTHORS <authors>` for a full list of contributors.

Please cite this repository as:

  .. code-block::

    Grosch, B., Ranzau, H., Dietrich, B., Kohne, T., Fuhrländer-Völker, D., Sossenheimer, J., Lindner, M., Weigold, M.
    A framework for researching energy optimization of factory operations.
    Energy Inform 5 (Suppl 1), 29 (2022). https://doi.org/10.1186/s42162-022-00207-6
