.. _entso-e_connection:

ENTSO-E Connection
======================
ENTSO-E Node
----------------------------------------------------
.. autoclass:: eta_connect.nodes::EntsoeNode
    :inherited-members:
    :exclude-members: get_eneffco_nodes_from_codes, from_dict, from_excel, protocol, as_dict, as_tuple, evolve
    :noindex:

ENTSO-E Connection
----------------------------------------------------
.. autoclass:: eta_connect.connections::EntsoeConnection
    :members:
    :noindex:

Example Usage
----------------------------------------------------
An example using the **ENTSO-E connection**:

.. literalinclude:: ../../examples/connections/read_series_entsoe.py
    :start-after: --begin_entsoe_doc_example--
    :end-before: --end_entsoe_doc_example--
    :dedent:
