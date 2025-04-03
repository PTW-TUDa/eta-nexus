.. _emonio_connection:

Emonio Connection
======================================
Eta-connect includes a connection class designed to read data from an Emonio device.
To ensure proper communication, the Emonio must be connected to the same network
as the machine running the eta-connect.
Additionally, because the EmonioConnection uses the Modbus protocol,
it is essential that the `Modbus Server` on the Emonio is set to `Enabled`.

This configuration can be done in the Emonio App by navigating to `Settings` -> `Modbus Server`.
The IP address and port of the Emonio can also be easily found within the app.

See the Emonio documentation for more information:
https://wiki.emonio.de/de/Emonio_P3

EmonioConnection
----------------------------------------------------
.. autoclass:: eta_connect.connections::EmonioConnection
    :members:
    :noindex:

.. _emonio_available_nodes:

.. list-table:: Available Emonio Nodes
    :widths: 10 90
    :header-rows: 1

    * - Allowed Names
      - Address
    * - 'VRMS', 'V_RMS', 'Voltage', 'V', 'Spannung'
      - 0
    * - 'IRMS', 'I_RMS', 'Current', 'I', 'Strom'
      - 2
    * - 'WATT', 'Power', 'W', 'Leistung', 'Wirkleistung'
      - 4
    * - 'VAR', 'Reactive Power', 'VAR', 'Blindleistung'
      - 6
    * - 'VA', 'Apparent Power', 'VA', 'Scheinleistung'
      - 8
    * - 'FREQ', 'Frequency', 'Hz', 'Frequenz'
      - 10
    * - 'KWH', 'Energy', 'kWh', 'Energie'
      - 12
    * - 'PF', 'Power Factor', 'PF', 'Leistungsfaktor'
      - 14
    * - 'VRMS MIN', 'VRMS_MIN', 'Voltage Min', 'V Min', 'Spannung Min'
      - 20
    * - 'VRMS MAX', 'VRMS_MAX', 'Voltage Max', 'V Max', 'Spannung Max'
      - 22
    * - 'IRMS MIN', 'IRMS_MIN', 'Current Min', 'I Min', 'Strom Min'
      - 24
    * - 'IRMS MAX', 'IRMS_MAX', 'Current Max', 'I Max', 'Strom Max'
      - 26
    * - 'WATT MIN', 'WATT_MIN', 'Power Min', 'W Min', 'Leistung Min'
      - 28
    * - 'WATT MAX', 'WATT_MAX', 'Power Max', 'W Max', 'Leistung Max'
      - 30
    * - 'Temp', 'degree', 'Temperature', '°C', 'Temperatur'
      - 500
    * - 'Impulse', 'Impuls'
      - 800


.. note::
    For reading MIN and MAX values, the phase must be specified. "abc" is not allowed.

.. autoclass:: eta_connect.connections.emonio_connection::ModbusNodeFactory
    :members:
    :noindex:

EmonioNode
----------------------------------------------------
.. autoclass:: eta_connect.nodes::EmonioNode
    :inherited-members:
    :exclude-members: get_eneffco_nodes_from_codes, from_dict, from_excel, protocol, as_dict, as_tuple, evolve  upper_cased
    :noindex:

Example Usage
--------------------------------------
This example demonstrates how to create a :class:`~eta_connect.connections.live_connect.LiveConnect` from a dictionary to read data from an Emonio device.
Alternatively, the LiveConnection can be created from a JSON file, with the JSON having the same structure as the dictionary.

``url`` has to be replaced with the IP address and port of the Emonio device, e.g. ``"192.168.178.123:502"``.

.. literalinclude:: ../../examples/connections/read_emonio_live.py
    :start-after: --live--
    :end-before: --live--
    :dedent:

Here we create the Emonio nodes manually and read them with the
:class:`~eta_connect.connections.EmonioConnection` class.

.. literalinclude:: ../../examples/connections/read_emonio_live.py
    :start-after: --emonio--
    :end-before: --emonio--
    :dedent:

The :class:`~eta_connect.connections.emonio_connection.ModbusNodeFactory` can be used to create modbus nodes directly.
But this is not recommended, as the :class:`~eta_connect.connections.EmonioConnection` class is more convenient and has extra error checking.

.. literalinclude:: ../../examples/connections/read_emonio_live.py
    :start-after: --modbus--
    :end-before: --modbus--
    :dedent:
