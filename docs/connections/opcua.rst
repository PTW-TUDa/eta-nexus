.. _Opcua_connection:

Opcua Connection
======================
OpcuaConnection
----------------------------------------------------

.. autoclass:: eta_nexus.connections::OpcuaConnection
    :members:
    :noindex:

OpcuaNode
----------------------------------------------------
.. autoclass:: eta_nexus.nodes::OpcuaNode
    :inherited-members:
    :exclude-members: get_eneffco_nodes_from_codes, from_dict, from_excel, protocol, as_dict, as_tuple
    :noindex:

Example Usage
----------------------------------------------------

Reading a single data point from an OPC UA server:

.. literalinclude:: ../../examples/connections/read_opcua.py
    :start-after: --begin_opcua_doc_read--
    :end-before: --end_opcua_doc_read--
    :dedent:

If you only need to read and do not want to create node objects yourself, build the
connection directly from a list of node ids:

.. literalinclude:: ../../examples/connections/read_opcua.py
    :start-after: --begin_opcua_doc_from_ids--
    :end-before: --end_opcua_doc_from_ids--
    :dedent:

Writing a value:

.. literalinclude:: ../../examples/connections/read_opcua.py
    :start-after: --begin_opcua_doc_write--
    :end-before: --end_opcua_doc_write--
    :dedent:

Subscribing to multiple nodes and collecting the values in a :py:class:`pandas.DataFrame`:

.. literalinclude:: ../../examples/connections/read_opcua.py
    :start-after: --begin_opcua_doc_subscribe--
    :end-before: --end_opcua_doc_subscribe--
    :dedent:
