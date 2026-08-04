.. _modbus_connection:

Modbus Connection
======================
ModbusConnection
----------------------------------------------------
.. autoclass:: eta_nexus.connections::ModbusConnection
    :members:
    :noindex:

ModbusNode
----------------------------------------------------
.. autoclass:: eta_nexus.nodes::ModbusNode
    :inherited-members:
    :exclude-members: get_eneffco_nodes_from_codes, from_dict, from_excel, protocol, as_dict, as_tuple, evolve
    :noindex:

Example Usage
----------------------------------------------------

Reading a single data point from a Modbus server:

.. literalinclude:: ../../examples/connections/read_modbus.py
    :start-after: --begin_modbus_doc_read--
    :end-before: --end_modbus_doc_read--
    :dedent:

Writing a value (only the ``coils`` and ``holding`` registers are writable):

.. literalinclude:: ../../examples/connections/read_modbus.py
    :start-after: --begin_modbus_doc_write--
    :end-before: --end_modbus_doc_write--
    :dedent:

Subscribing to multiple nodes and collecting the values in a :py:class:`pandas.DataFrame`:

.. literalinclude:: ../../examples/connections/read_modbus.py
    :start-after: --begin_modbus_doc_subscribe--
    :end-before: --end_modbus_doc_subscribe--
    :dedent:
