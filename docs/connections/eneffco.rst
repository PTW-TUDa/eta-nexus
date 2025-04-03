.. _eneffco_connection:

Eneffco Connection
======================
EneffcoConnection
----------------------------------------------------
.. autoclass:: eta_connect.connections::EneffcoConnection
    :members:
    :noindex:

EneffcoNode
----------------------------------------------------
.. autoclass:: eta_connect.nodes::EneffcoNode
    :inherited-members:
    :exclude-members: get_eneffco_nodes_from_codes, from_dict, from_excel, protocol, as_dict, as_tuple, evolve
    :noindex:

Example Usage
----------------------------------------------------
A simple example using the **Eneffco Connection**:

.. literalinclude:: ../../examples/connections/read_series_eneffco.py
    :start-after: --main--
    :end-before: --main--
    :dedent:
