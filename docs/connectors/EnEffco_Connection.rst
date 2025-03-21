.. _eneffco_connection:

EnEffco Connection
======================
EnEffCoConnection
----------------------------------------------------
.. autoclass:: eta_connect.connectors::EnEffCoConnection
    :members:
    :noindex:

NodeEnEffCo
----------------------------------------------------
.. autoclass:: eta_connect.connectors.node::NodeEnEffCo
    :inherited-members:
    :exclude-members: get_eneffco_nodes_from_codes, from_dict, from_excel, protocol, as_dict, as_tuple, evolve
    :noindex:

Example Usage
----------------------------------------------------
A simple example using the **EnEffCo connection**:

.. literalinclude:: ../../examples/connectors/read_series_eneffco.py
    :start-after: --main--
    :end-before: --main--
    :dedent:
